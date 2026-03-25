"""
Script: ci_tools/main_check_candidate_akmods_cache.py
What: Checks whether akmods cache can be reused for the current base-image kernels.
Doing: Prefers lightweight metadata labels on the shared cache image and falls back to unpacking layers when older images do not expose that metadata.
Why: Skip rebuild when safe, but rebuild when any required module set is stale.
Goal: Control main-workflow rebuild decisions.
"""

from __future__ import annotations
from dataclasses import dataclass
import tempfile
from pathlib import Path

from ci_tools.common import (
    AKMODS_CACHE_KERNEL_RELEASES_LABEL,
    AKMODS_CACHE_METADATA_VERSION,
    AKMODS_CACHE_METADATA_VERSION_LABEL,
    CiToolError,
    kernel_releases_from_env,
    load_layer_files_from_oci_layout,
    normalize_owner,
    optional_env,
    optional_registry_creds,
    require_env,
    skopeo_copy,
    skopeo_exists,
    skopeo_inspect_json,
    sort_kernel_releases,
    unpack_layer_tarballs,
    write_github_outputs,
)


@dataclass(frozen=True)
class AkmodsCacheStatus:
    """
    Result of checking one shared akmods cache image against required kernels.

    `image_exists` tells us whether the source tag is present at all.
    `missing_releases` is the fail-closed list of kernels not covered by that
    image. A reusable cache must satisfy both conditions.
    """

    source_image: str
    image_exists: bool
    missing_releases: tuple[str, ...]

    @property
    def reusable(self) -> bool:
        """True only when the cache exists and covers every required kernel."""

        return self.image_exists and not self.missing_releases


def write_cache_status_outputs(status: AkmodsCacheStatus) -> None:
    """Write the cache result in both legacy and structured output forms."""

    reusable = "true" if status.reusable else "false"
    if not status.image_exists:
        status_name = "missing_image"
    elif status.reusable:
        status_name = "reusable"
    else:
        status_name = "stale"

    write_github_outputs(
        {
            "exists": reusable,
            "status": status_name,
            "missing_releases": " ".join(status.missing_releases),
            "source_image": status.source_image,
        }
    )


def _has_kernel_matching_rpm(root_dir: Path, kernel_release: str) -> bool:
    # We only trust cache reuse when an RPM exists for this exact kernel string.
    # If the cache only has RPMs for older kernels, that cache is "stale".
    rpm_dir = root_dir / "rpms" / "kmods" / "zfs"
    if not rpm_dir.exists():
        return False
    pattern = f"kmod-zfs-{kernel_release}-*.rpm"
    return any(rpm_dir.glob(pattern))


def _missing_kernel_releases(root_dir: Path, kernel_releases: list[str]) -> list[str]:
    """
    Return kernel releases that do not have a matching cached kmod RPM.

    This keeps the main workflow fail-closed: one missing kernel means the cache
    is not good enough for the current base image.
    """
    return [release for release in kernel_releases if not _has_kernel_matching_rpm(root_dir, release)]


def _kernel_releases_from_metadata_labels(inspect_json: dict) -> tuple[str, ...] | None:
    """
    Return kernel releases advertised in shared-cache labels, if present.

    Newer shared cache images publish lightweight labels that list the exact
    kernel releases covered by the merged RPM payloads. When those labels are
    present, the cache check can stay on the `skopeo inspect` fast path instead
    of downloading and unpacking the whole image.
    """

    labels = inspect_json.get("Labels")
    if not isinstance(labels, dict):
        return None

    metadata_version = str(labels.get(AKMODS_CACHE_METADATA_VERSION_LABEL) or "")
    if metadata_version != AKMODS_CACHE_METADATA_VERSION:
        return None

    kernel_releases = [
        value
        for value in str(labels.get(AKMODS_CACHE_KERNEL_RELEASES_LABEL) or "").split()
        if value
    ]
    if not kernel_releases:
        return None

    return tuple(sort_kernel_releases(kernel_releases))


def _missing_required_kernel_releases(
    required_kernel_releases: list[str],
    present_kernel_releases: tuple[str, ...],
) -> tuple[str, ...]:
    """Return required kernels that are not listed in one present-kernel set."""

    present = set(present_kernel_releases)
    return tuple(
        release for release in required_kernel_releases if release not in present
    )


def inspect_candidate_akmods_cache(
    *,
    image_org: str,
    source_repo: str,
    fedora_version: str,
    kernel_releases: list[str],
    creds: str | None = None,
) -> AkmodsCacheStatus:
    """
    Inspect one shared akmods cache image and report whether it is reusable.

    This helper is shared by the main workflow and the read-only validation
    workflows so they all make the same cache-reuse decision.
    """

    source_image = f"ghcr.io/{image_org}/{source_repo}:main-{fedora_version}"
    resolved_creds = creds if creds is not None else optional_registry_creds()
    if not skopeo_exists(f"docker://{source_image}", creds=resolved_creds):
        return AkmodsCacheStatus(
            source_image=source_image,
            image_exists=False,
            missing_releases=tuple(kernel_releases),
        )

    inspect_json = skopeo_inspect_json(
        f"docker://{source_image}",
        creds=resolved_creds,
    )
    metadata_kernel_releases = _kernel_releases_from_metadata_labels(inspect_json)
    if metadata_kernel_releases is not None:
        print(f"Using cache metadata labels from {source_image} for kernel coverage check.")
        return AkmodsCacheStatus(
            source_image=source_image,
            image_exists=True,
            missing_releases=_missing_required_kernel_releases(
                kernel_releases,
                metadata_kernel_releases,
            ),
        )

    print(f"No cache metadata labels found on {source_image}; falling back to layer scan.")
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        akmods_dir = root / "akmods"
        # `skopeo copy ... dir:<path>` saves image layers so we can inspect files.
        skopeo_copy(
            f"docker://{source_image}",
            f"dir:{akmods_dir}",
            creds=resolved_creds,
        )

        layer_files = load_layer_files_from_oci_layout(akmods_dir)
        # Extract all filesystem layers into one temp tree for file checks.
        unpack_layer_tarballs(layer_files, root)

        missing_releases = _missing_kernel_releases(root, kernel_releases)
        return AkmodsCacheStatus(
            source_image=source_image,
            image_exists=True,
            missing_releases=tuple(missing_releases),
        )


def main() -> None:
    # Workflow-provided inputs.
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    fedora_version = require_env("FEDORA_VERSION")
    # `KERNEL_RELEASES` is the preferred input because one base image can carry
    # more than one installed kernel under `/lib/modules`.
    kernel_releases = kernel_releases_from_env()
    if not kernel_releases:
        raise CiToolError("Expected at least one kernel release from workflow env")
    # Keep backward compatibility with older workflow env name:
    # - prefer `AKMODS_REPO` (generic source repo name)
    # - fallback to `CANDIDATE_AKMODS_REPO` (older name)
    source_repo = optional_env("AKMODS_REPO") or require_env("CANDIDATE_AKMODS_REPO")

    # Source cache image reference for this Fedora major stream.
    # If source cache is missing/stale, workflow needs an akmods rebuild.
    # "Stale" means cache content was built for an older kernel release.
    status = inspect_candidate_akmods_cache(
        image_org=image_org,
        source_repo=source_repo,
        fedora_version=fedora_version,
        kernel_releases=kernel_releases,
    )

    if not status.image_exists:
        # Source cache image is missing, so downstream build must rebuild it.
        # We write `exists=false` to GitHub step outputs so workflow `if:` rules
        # can react without parsing log text.
        write_cache_status_outputs(status)
        print(f"No existing source akmods cache image for Fedora {fedora_version}; rebuild is required.")
        return

    if status.reusable:
        # `exists=true` means this cache can be safely reused.
        write_cache_status_outputs(status)
        print(
            f"Found matching {status.source_image} kmods for kernels {' '.join(kernel_releases)}; "
            "akmods rebuild can be skipped."
        )
        return

    # `exists=false` here means the cache exists but is stale (wrong kernel).
    write_cache_status_outputs(status)
    print(
        f"Cached {status.source_image} is present but missing kmods for kernels "
        f"{' '.join(status.missing_releases)}; "
        "akmods rebuild is required."
    )


if __name__ == "__main__":
    main()
