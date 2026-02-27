from __future__ import annotations

import os
from pathlib import Path

from ci_tools.common import CiToolError, normalize_owner, require_env, run_cmd


AKMODS_WORKTREE = Path("/tmp/akmods")
IMAGES_YAML = AKMODS_WORKTREE / "images.yaml"


def main() -> None:
    # Inputs passed from workflow env.
    fedora_version = require_env("FEDORA_VERSION")
    akmods_repo = require_env("AKMODS_REPO")
    akmods_description = require_env("AKMODS_DESCRIPTION")
    # Normalize owner means: convert to lowercase for consistent registry paths.
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))

    if not IMAGES_YAML.exists():
        raise CiToolError(f"Expected akmods images file at {IMAGES_YAML}")

    # `yq` expression uses environment variables via `strenv(...)`.
    os.environ["FEDORA_VERSION"] = fedora_version
    os.environ["IMAGE_ORG"] = image_org
    os.environ["AKMODS_REPO"] = akmods_repo
    os.environ["AKMODS_DESCRIPTION"] = akmods_description

    yq_expression = """
      .images[strenv(FEDORA_VERSION)].main.zfs = {
        "org": strenv(IMAGE_ORG),
        "registry": "ghcr.io",
        "repo": "akmods",
        "transport": "docker://",
        "name": strenv(AKMODS_REPO),
        "description": strenv(AKMODS_DESCRIPTION),
        "architecture": ["x86_64"]
      }
    """
    run_cmd(["yq", "-i", yq_expression, str(IMAGES_YAML)], capture_output=False)

    # Print final block so logs show the effective output destination.
    updated_block = run_cmd(
        ["yq", f'.images["{fedora_version}"].main.zfs', str(IMAGES_YAML)],
    ).strip()
    if updated_block:
        print(updated_block)


if __name__ == "__main__":
    main()
