from __future__ import annotations

import re

from ci_tools.common import require_env, write_github_outputs


UNSAFE_CHARS_RE = re.compile(r"[^a-z0-9._-]+")
MAX_LENGTH = 120
SHARED_BRANCH_AKMODS_REPO = "akmods-zfs-candidate"


def sanitize_branch_name(branch: str) -> str:
    """Convert a branch name into a registry-safe identifier."""
    # Lowercase + replace unsupported chars with '-' so tags/repo names are valid.
    safe = UNSAFE_CHARS_RE.sub("-", branch.lower()).strip("-")
    return safe or "branch"


def clamp_tag(value: str, fallback: str) -> str:
    """Truncate and clean a tag/repository string while preserving a fallback."""
    # Keep names short and avoid trailing '-' after truncation.
    trimmed = value[:MAX_LENGTH].rstrip("-")
    return trimmed or fallback


def build_branch_metadata(branch_name: str) -> tuple[str, str, str]:
    # Return three values as a tuple:
    # 1) image tag for BlueBuild output
    # 2) akmods repository name
    # 3) branch-specific akmods tag prefix
    # Branch akmods now use one shared repo plus branch-specific tags.
    # This avoids creating new per-branch package repos that default to private
    # visibility and can fail later pulls with 403 during image compose.
    safe_branch = sanitize_branch_name(branch_name)
    image_tag = clamp_tag(f"beta-{safe_branch}", "beta-branch")
    akmods_tag_prefix = clamp_tag(f"br-{safe_branch}", "br-branch")
    return image_tag, SHARED_BRANCH_AKMODS_REPO, akmods_tag_prefix


def main() -> None:
    # GitHub sets this to the branch name that triggered the run.
    branch_name = require_env("GITHUB_REF_NAME")
    image_tag, akmods_repo, akmods_tag_prefix = build_branch_metadata(branch_name)

    # Export all values so downstream jobs can reference them.
    write_github_outputs(
        {
            "image_tag": image_tag,
            "akmods_repo": akmods_repo,
            "akmods_tag_prefix": akmods_tag_prefix,
        }
    )
    print(f"Branch image tag: {image_tag}")
    print(f"Branch akmods repo: {akmods_repo}")
    print(f"Branch akmods tag prefix: {akmods_tag_prefix}")


if __name__ == "__main__":
    main()
