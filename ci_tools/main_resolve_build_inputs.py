"""
Script: ci_tools/main_resolve_build_inputs.py
What: Selects and validates the exact image inputs for one workflow run.
Doing: Uses lock-file replay values (when enabled) or defaults, resolves digests/tags, and exports outputs for later jobs.
Why: Keeps every job in the run aligned to the same base and builder inputs.
Goal: Export trusted input values that downstream jobs can reuse safely.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from ci_tools.common import (
    CiToolError,
    extract_fedora_version,
    optional_env,
    require_env,
    skopeo_inspect_digest,
    skopeo_inspect_json,
    write_github_outputs,
)

TAG_FROM_REF_RE = re.compile(r"^[^@]+:([^/@]+)$")
DATE_STAMPED_TAG_RE = re.compile(r"-[0-9]{8}(\.[0-9]+)?$")
VERSION_LABEL_RE = re.compile(r"^[0-9]+\.[0-9]{8}(\.[0-9]+)?$")


def extract_source_tag(image_ref: str) -> str:
    """Return the tag from an image ref like `name:tag`, or empty string."""
    match = TAG_FROM_REF_RE.match(image_ref)
    return match.group(1) if match else ""


def choose_base_image_tag(
    *,
    source_tag: str,
    version_label: str,
    fedora_version: str,
    expected_digest: str,
    digest_lookup: Callable[[str], str],
) -> tuple[str, list[str]]:
    """
    Pick a stable base tag for this run.

    Rules:
    - If the source tag is already date-stamped, keep it.
    - Otherwise derive candidate tags from version label and choose the one
      that resolves to the expected digest.
    """
    # If we already got a date-stamped tag, treat it as stable for this run.
    if source_tag and DATE_STAMPED_TAG_RE.search(source_tag):
        return source_tag, [source_tag]

    if not VERSION_LABEL_RE.match(version_label):
        raise CiToolError(
            "Failed to derive immutable base tag from "
            f"org.opencontainers.image.version={version_label}"
        )

    # Example label: 43.20260227.1
    # We only need the suffix part (20260227.1) to build candidate tags.
    version_suffix = version_label.split(".", 1)[1]
    candidate_tags: list[str] = []
    if source_tag:
        candidate_tags.append(f"{source_tag}-{version_suffix}")
    candidate_tags.extend([f"latest-{version_suffix}", f"{fedora_version}-{version_suffix}"])

    # Try each candidate tag and keep the first one that resolves to the same digest.
    # Digest match is the key safety check: tag text can move, digest does not.
    for candidate_tag in candidate_tags:
        candidate_digest = digest_lookup(candidate_tag)
        if candidate_digest == expected_digest:
            return candidate_tag, candidate_tags

    raise CiToolError(
        f"Failed to map digest {expected_digest} to an immutable tag. "
        f"Tried candidate tags: {' '.join(candidate_tags)}"
    )


def _load_lock_file(lock_file_path: str) -> dict:
    # Lock file is a plain JSON object saved from a previous run.
    lock_path = Path(lock_file_path)
    if not lock_path.exists():
        raise CiToolError(f"Replay lock file not found: {lock_file_path}")
    with lock_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    # Workflow inputs are supplied through environment variables.
    use_input_lock = optional_env("USE_INPUT_LOCK", "false").lower() == "true"
    lock_file_path = require_env("LOCK_FILE")
    build_container_ref = require_env("BUILD_CONTAINER_REF")

    if use_input_lock:
        # Replay mode: load values from `ci/inputs.lock.json` (or another lock file).
        # This is how we rebuild with the exact same inputs as an older run.
        lock_data = _load_lock_file(lock_file_path)
        base_image_ref = str(lock_data.get("base_image") or "")
        lock_build_container_ref = str(lock_data.get("build_container") or "")
        zfs_minor_version = str(lock_data.get("zfs_minor_version") or "")
        akmods_upstream_ref = str(lock_data.get("akmods_upstream_ref") or "")

        if not base_image_ref:
            raise CiToolError("Lock file missing required field: base_image")
        if "REPLACE_ME" in base_image_ref:
            raise CiToolError("Lock file base_image still contains placeholder value")
        if lock_build_container_ref and "REPLACE_ME" in lock_build_container_ref:
            raise CiToolError("Lock file build_container still contains placeholder value")

        if lock_build_container_ref and build_container_ref != lock_build_container_ref:
            raise CiToolError(
                "Replay mismatch: build container input "
                f"({build_container_ref}) does not match lock file "
                f"({lock_build_container_ref}). Set workflow input "
                f"build_container_image={lock_build_container_ref} when use_input_lock=true."
            )

        # Lock files can leave some fields empty; default them when missing.
        if not zfs_minor_version:
            zfs_minor_version = require_env("DEFAULT_ZFS_MINOR_VERSION")
        if not akmods_upstream_ref:
            akmods_upstream_ref = require_env("DEFAULT_AKMODS_REF")
    else:
        # Normal mode: resolve from configured defaults (moving tags).
        base_image_ref = require_env("DEFAULT_BASE_IMAGE")
        zfs_minor_version = require_env("DEFAULT_ZFS_MINOR_VERSION")
        akmods_upstream_ref = require_env("DEFAULT_AKMODS_REF")

    # Read base image metadata from registry.
    # Labels carry kernel information and stream version information.
    base_inspect_json = skopeo_inspect_json(f"docker://{base_image_ref}")
    base_image_name = str(base_inspect_json.get("Name") or "")
    base_image_digest = str(base_inspect_json.get("Digest") or "")
    labels = base_inspect_json.get("Labels") or {}
    kernel_release = str(labels.get("ostree.linux") or "")
    base_image_version_label = str(labels.get("org.opencontainers.image.version") or "")

    if not base_image_name or not base_image_digest:
        raise CiToolError(f"Failed to resolve base image digest for {base_image_ref}")
    if not kernel_release:
        raise CiToolError(f"Failed to read ostree.linux label from {base_image_ref}")

    fedora_version = extract_fedora_version(kernel_release)
    base_image_pinned = f"{base_image_name}@{base_image_digest}"
    source_tag = extract_source_tag(base_image_ref)

    # Helper function:
    # input tag -> lookup digest in registry.
    # Return empty string when lookup fails so tag selection can continue.
    def lookup_digest(candidate_tag: str) -> str:
        candidate_ref = f"docker://{base_image_name}:{candidate_tag}"
        try:
            return skopeo_inspect_digest(candidate_ref)
        except CiToolError:
            return ""

    base_image_tag, candidate_tags = choose_base_image_tag(
        source_tag=source_tag,
        version_label=base_image_version_label,
        fedora_version=fedora_version,
        expected_digest=base_image_digest,
        digest_lookup=lookup_digest,
    )

    # Final safety check: chosen tag must still match the expected digest.
    selected_tag_digest = lookup_digest(base_image_tag)
    if selected_tag_digest != base_image_digest:
        raise CiToolError(
            f"Resolved tag {base_image_name}:{base_image_tag} does not match digest {base_image_digest}"
        )

    build_container_inspect = skopeo_inspect_json(f"docker://{build_container_ref}")
    build_container_name = str(build_container_inspect.get("Name") or "")
    build_container_digest = str(build_container_inspect.get("Digest") or "")

    if not build_container_name or not build_container_digest:
        raise CiToolError(f"Failed to resolve build container digest for {build_container_ref}")

    build_container_pinned = f"{build_container_name}@{build_container_digest}"

    # Export resolved values for downstream workflow steps.
    write_github_outputs(
        {
            "version": fedora_version,
            "kernel_release": kernel_release,
            "base_image_ref": base_image_ref,
            "base_image_name": base_image_name,
            "base_image_tag": base_image_tag,
            "base_image_pinned": base_image_pinned,
            "base_image_digest": base_image_digest,
            "build_container_ref": build_container_ref,
            "build_container_pinned": build_container_pinned,
            "build_container_digest": build_container_digest,
            "zfs_minor_version": zfs_minor_version,
            "akmods_upstream_ref": akmods_upstream_ref,
            "use_input_lock": "true" if use_input_lock else "false",
            "lock_file_path": lock_file_path,
        }
    )

    print(f"Resolved base image: {base_image_pinned}")
    print(f"Resolved base image tag: {base_image_name}:{base_image_tag}")
    print(f"Resolved build container: {build_container_pinned}")
    print(f"Kernel release: {kernel_release}")
    print(f"Fedora version: {fedora_version}")
    print(f"ZFS minor version: {zfs_minor_version}")

    # Helpful for debugging: shows exactly which tags were considered.
    if candidate_tags:
        print(f"Base-tag candidates checked: {' '.join(candidate_tags)}")


if __name__ == "__main__":
    main()
