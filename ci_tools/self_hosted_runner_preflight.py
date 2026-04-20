"""
Script: ci_tools/self_hosted_runner_preflight.py
What: Performs lightweight hygiene and disk preflight checks on self-hosted runners.
Doing: Removes stale repo-owned temp directories, prunes unused Podman images, prints storage context, and fails early when free workspace space is below a configured threshold.
Why: Persistent self-hosted runners accumulate state that can turn later builds flaky or slow.
Goal: Catch disk-pressure issues before heavy jobs start and keep stale temp leftovers from piling up.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import time

from ci_tools.common import CiToolError, optional_env, require_env, run_cmd


STALE_TEMP_PREFIXES = (
    "akmods-merge-",
    "candidate-image-smoke-",
)
BYTES_PER_GIB = 1024**3


@dataclass(frozen=True)
class CleanupSummary:
    """Summary of stale temporary directories removed during preflight."""

    removed_paths: tuple[str, ...]
    reclaimed_bytes: int


@dataclass(frozen=True)
class PodmanPruneSummary:
    """Summary of one Podman image-prune pass."""

    command: tuple[str, ...]
    removed_references: int
    reclaimed_bytes: int
    skipped_reason: str = ""


@dataclass(frozen=True)
class RunnerPreflightSummary:
    """Result of the self-hosted runner preflight check."""

    workspace_path: str
    host_tmp_path: str
    free_bytes: int
    required_free_bytes: int
    cleanup: CleanupSummary
    podman_prunes: tuple[PodmanPruneSummary, ...]


def format_bytes(value: int) -> str:
    """Return one human-readable binary size string."""

    if value < BYTES_PER_GIB:
        return f"{value / (1024**2):.1f} MiB"
    return f"{value / BYTES_PER_GIB:.1f} GiB"


def _path_size_bytes(path: Path) -> int:
    """Return the total on-disk size for one file or directory tree."""

    if path.is_symlink():
        return 0
    if path.is_file():
        return path.stat().st_size

    total = 0
    for entry in path.rglob("*"):
        if entry.is_symlink() or not entry.is_file():
            continue
        total += entry.stat().st_size
    return total


def cleanup_stale_temp_dirs(
    temp_root: Path,
    *,
    prefixes: tuple[str, ...] = STALE_TEMP_PREFIXES,
    retention_hours: int = 24,
    now_timestamp: float | None = None,
) -> CleanupSummary:
    """
    Delete stale repo-owned temp directories under one temp root.

    The repo's Python helpers already use dedicated prefixes for their temp
    directories. Removing only those older leftovers avoids broad cleanup of
    unrelated runner state while still reclaiming space after interrupted jobs.
    """

    if not temp_root.exists():
        return CleanupSummary(removed_paths=(), reclaimed_bytes=0)

    now = time.time() if now_timestamp is None else now_timestamp
    cutoff_seconds = retention_hours * 3600
    removed_paths: list[str] = []
    reclaimed_bytes = 0

    for prefix in prefixes:
        for candidate in sorted(temp_root.glob(f"{prefix}*")):
            if not candidate.exists() or not candidate.is_dir():
                continue

            age_seconds = now - candidate.stat().st_mtime
            if age_seconds < cutoff_seconds:
                continue

            reclaimed_bytes += _path_size_bytes(candidate)
            shutil.rmtree(candidate, ignore_errors=True)
            removed_paths.append(str(candidate))

    return CleanupSummary(
        removed_paths=tuple(removed_paths),
        reclaimed_bytes=reclaimed_bytes,
    )


def _bool_from_env(value: str, *, default: bool) -> bool:
    """Parse one GitHub Actions string boolean."""

    normalized = value.strip().lower()
    if not normalized:
        return default
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise CiToolError(f"Expected boolean value, got: {value}")


def prune_unused_podman_images(
    *,
    workspace: Path,
    older_than_hours: int | None,
) -> PodmanPruneSummary:
    """
    Remove unused Podman images and report the approximate reclaimed space.

    Persistent self-hosted runners keep `/var/lib/containers` between jobs. The
    images are safe to prune here because this only removes image references not
    used by containers. The free-space delta is measured from the workspace
    filesystem because the runner workspace and container storage are expected
    to live on the same VM disk.
    """

    if shutil.which("podman") is None:
        return PodmanPruneSummary(
            command=(),
            removed_references=0,
            reclaimed_bytes=0,
            skipped_reason="podman is not installed",
        )

    command = [
        "podman",
        "image",
        "prune",
        "--all",
        "--force",
        "--build-cache",
    ]
    if older_than_hours is not None:
        command.extend(["--filter", f"until={older_than_hours}h"])

    before_free = shutil.disk_usage(workspace).free
    try:
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        details = stderr or stdout or str(exc)
        raise CiToolError(
            f"Failed to prune unused Podman images: {' '.join(command)}\n{details}"
        ) from exc

    after_free = shutil.disk_usage(workspace).free
    removed_references = len(
        [line for line in result.stdout.splitlines() if line.strip()]
    )
    return PodmanPruneSummary(
        command=tuple(command),
        removed_references=removed_references,
        reclaimed_bytes=max(0, after_free - before_free),
    )


def run_preflight(
    *,
    workspace: Path,
    host_root: Path,
    min_free_gib: int,
    retention_hours: int,
    prune_podman_images: bool = True,
    podman_image_retention_hours: int = 24,
    aggressive_podman_prune_on_low_space: bool = True,
    now_timestamp: float | None = None,
) -> RunnerPreflightSummary:
    """Run the cleanup-plus-free-space check and return a summary object."""

    host_tmp_path = host_root / "tmp"
    cleanup = cleanup_stale_temp_dirs(
        host_tmp_path,
        retention_hours=retention_hours,
        now_timestamp=now_timestamp,
    )

    required_free_bytes = min_free_gib * BYTES_PER_GIB
    podman_prunes: list[PodmanPruneSummary] = []

    if prune_podman_images:
        podman_prunes.append(
            prune_unused_podman_images(
                workspace=workspace,
                older_than_hours=podman_image_retention_hours,
            )
        )

    free_bytes = shutil.disk_usage(workspace).free
    if (
        prune_podman_images
        and aggressive_podman_prune_on_low_space
        and free_bytes < required_free_bytes
    ):
        podman_prunes.append(
            prune_unused_podman_images(
                workspace=workspace,
                older_than_hours=None,
            )
        )
        free_bytes = shutil.disk_usage(workspace).free

    return RunnerPreflightSummary(
        workspace_path=str(workspace),
        host_tmp_path=str(host_tmp_path),
        free_bytes=free_bytes,
        required_free_bytes=required_free_bytes,
        cleanup=cleanup,
        podman_prunes=tuple(podman_prunes),
    )


def _print_runner_storage_context(*, workspace: Path, host_root: Path) -> None:
    """Print lightweight disk context that helps operators debug runner pressure."""

    for path in (workspace, host_root / "tmp", host_root / "var" / "lib" / "containers"):
        if not path.exists():
            continue
        print(run_cmd(["df", "-h", str(path)]).strip())

    if shutil.which("podman") is None:
        return

    try:
        print(run_cmd(["podman", "system", "df"]).strip())
    except CiToolError as exc:
        print(f"Warning: failed to collect podman storage stats: {exc}")


def main() -> None:
    workspace = Path(require_env("GITHUB_WORKSPACE"))
    host_root = Path(optional_env("RUNNER_HOST_ROOT", "/")).resolve()
    min_free_gib = int(optional_env("RUNNER_MIN_FREE_GB", "20"))
    retention_hours = int(optional_env("RUNNER_TEMP_RETENTION_HOURS", "24"))
    prune_podman_images = _bool_from_env(
        optional_env("RUNNER_PRUNE_PODMAN_IMAGES", "true"),
        default=True,
    )
    podman_image_retention_hours = int(
        optional_env("RUNNER_PODMAN_IMAGE_RETENTION_HOURS", "24")
    )
    aggressive_podman_prune_on_low_space = _bool_from_env(
        optional_env("RUNNER_AGGRESSIVE_PODMAN_PRUNE_ON_LOW_SPACE", "true"),
        default=True,
    )

    summary = run_preflight(
        workspace=workspace,
        host_root=host_root,
        min_free_gib=min_free_gib,
        retention_hours=retention_hours,
        prune_podman_images=prune_podman_images,
        podman_image_retention_hours=podman_image_retention_hours,
        aggressive_podman_prune_on_low_space=aggressive_podman_prune_on_low_space,
    )

    print(f"Runner workspace path: {summary.workspace_path}")
    print(f"Runner host temp root: {summary.host_tmp_path}")
    print(
        "Workspace filesystem free space: "
        f"{format_bytes(summary.free_bytes)} "
        f"(required minimum: {format_bytes(summary.required_free_bytes)})"
    )

    if summary.cleanup.removed_paths:
        print(
            "Removed stale temp directories: "
            + ", ".join(summary.cleanup.removed_paths)
        )
        print(
            "Reclaimed temporary space: "
            f"{format_bytes(summary.cleanup.reclaimed_bytes)}"
        )
    else:
        print("No stale repo-owned temp directories needed cleanup.")

    for podman_prune in summary.podman_prunes:
        if podman_prune.skipped_reason:
            print(f"Skipped Podman image pruning: {podman_prune.skipped_reason}.")
            continue
        print(
            "Pruned unused Podman images with "
            f"`{' '.join(podman_prune.command)}`: "
            f"{podman_prune.removed_references} references removed, "
            f"approximately {format_bytes(podman_prune.reclaimed_bytes)} reclaimed."
        )

    _print_runner_storage_context(workspace=workspace, host_root=host_root)

    if summary.free_bytes < summary.required_free_bytes:
        raise CiToolError(
            "Self-hosted runner does not have enough free workspace space: "
            f"{format_bytes(summary.free_bytes)} available, "
            f"{format_bytes(summary.required_free_bytes)} required."
        )


if __name__ == "__main__":
    main()
