from __future__ import annotations

from ci_tools.common import normalize_owner, require_env, skopeo_copy


def main() -> None:
    # Inputs from the branch workflow step.
    # `SOURCE_AKMODS_REPO` is the shared source repo that already contains
    # kernel-matched akmods tags (for example `akmods-zfs:main-43`).
    # `DEST_AKMODS_REPO` is the public repo used by branch compose.
    # Compose step here means the branch image build stage.
    # Note: source-code repo visibility and container package visibility are
    # separate. We use this alias copy so compose reads a known accessible tag.
    fedora_version = require_env("FEDORA_VERSION")
    source_akmods_repo = require_env("SOURCE_AKMODS_REPO")
    dest_akmods_repo = require_env("DEST_AKMODS_REPO")
    dest_tag_prefix = require_env("DEST_TAG_PREFIX")

    # GitHub provides actor/token in workflow env.
    # We use the same credentials for source read and destination write.
    registry_actor = require_env("REGISTRY_ACTOR")
    registry_token = require_env("REGISTRY_TOKEN")
    creds = f"{registry_actor}:{registry_token}"

    # Normalize owner means: convert to lowercase for consistent image paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))

    # Source tag comes from upstream akmods naming (`main-<fedora>`).
    # Destination tag is branch-scoped and public (`br-<branch>-<fedora>`).
    source_ref = f"docker://ghcr.io/{image_org}/{source_akmods_repo}:main-{fedora_version}"
    dest_ref = f"docker://ghcr.io/{image_org}/{dest_akmods_repo}:{dest_tag_prefix}-{fedora_version}"

    skopeo_copy(source_ref, dest_ref, creds=creds)
    print(f"Published branch akmods alias: {source_ref} -> {dest_ref}")


if __name__ == "__main__":
    main()
