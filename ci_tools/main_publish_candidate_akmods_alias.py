"""
Script: ci_tools/main_publish_candidate_akmods_alias.py
What: Publishes candidate akmods alias tags from shared source tags.
Doing: Copies Fedora-wide and kernel-matched source tags into candidate repo tags.
Why: Candidate compose and promotion expect candidate-repo tag names.
Goal: Keep candidate flow using the correct akmods content for this kernel.
"""

from __future__ import annotations

from ci_tools.common import CiToolError, normalize_owner, require_env, skopeo_copy


def kernel_source_tag_candidates(*, fedora_version: str, kernel_release: str) -> list[str]:
    """
    Build possible source tags for kernel-specific akmods content.

    We prefer the full kernel string (includes architecture suffix).
    Some upstream publish paths can also use a no-architecture variant, so we
    keep that as a fallback candidate.
    """
    candidates = [f"main-{fedora_version}-{kernel_release}"]
    if kernel_release.endswith(".x86_64") or kernel_release.endswith(".aarch64"):
        kernel_without_arch = kernel_release.rsplit(".", 1)[0]
        candidates.append(f"main-{fedora_version}-{kernel_without_arch}")
    return candidates


def main() -> None:
    # Inputs from workflow env.
    # - source repo: where akmods build actually published tags
    # - destination repo: candidate repo used by candidate compose/promotion
    # Compose step here means the candidate image build stage.
    fedora_version = require_env("FEDORA_VERSION")
    kernel_release = require_env("KERNEL_RELEASE")
    source_akmods_repo = require_env("SOURCE_AKMODS_REPO")
    dest_akmods_repo = require_env("DEST_AKMODS_REPO")

    # GitHub provides actor/token in workflow env.
    registry_actor = require_env("REGISTRY_ACTOR")
    registry_token = require_env("REGISTRY_TOKEN")
    creds = f"{registry_actor}:{registry_token}"

    # Normalize owner means: convert to lowercase for consistent image paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))

    # Always alias the Fedora-wide cache tag.
    # "Alias tag" here means:
    # we copy one image reference to another tag so both tags point to the same
    # image content (same digest), without rebuilding.
    shared_source_ref = f"docker://ghcr.io/{image_org}/{source_akmods_repo}:main-{fedora_version}"
    candidate_dest_ref = f"docker://ghcr.io/{image_org}/{dest_akmods_repo}:main-{fedora_version}"
    skopeo_copy(shared_source_ref, candidate_dest_ref, creds=creds)
    print(f"Published candidate alias: {shared_source_ref} -> {candidate_dest_ref}")

    # Alias the kernel-matched tag used by compose.
    # This keeps candidate compose pinned to the same kernel-specific kmods that
    # were validated, while still reading from the candidate repo path.
    destination_kernel_ref = (
        f"docker://ghcr.io/{image_org}/{dest_akmods_repo}:main-{fedora_version}-{kernel_release}"
    )
    source_kernel_tags = kernel_source_tag_candidates(
        fedora_version=fedora_version,
        kernel_release=kernel_release,
    )

    # Try candidates in order and stop on first success.
    # Keep a readable list of failure messages so we can show exactly what was
    # attempted if none of the possible source tags exist.
    copy_errors: list[str] = []
    for source_kernel_tag in source_kernel_tags:
        source_kernel_ref = f"docker://ghcr.io/{image_org}/{source_akmods_repo}:{source_kernel_tag}"
        try:
            skopeo_copy(source_kernel_ref, destination_kernel_ref, creds=creds)
            print(f"Published candidate alias: {source_kernel_ref} -> {destination_kernel_ref}")
            return
        except CiToolError as exc:
            copy_errors.append(f"{source_kernel_ref}: {exc}")

    joined_errors = "\n".join(copy_errors)
    raise CiToolError(
        "Failed to publish candidate kernel-matched akmods alias. "
        f"Tried source tags: {', '.join(source_kernel_tags)}\n{joined_errors}"
    )


if __name__ == "__main__":
    main()
