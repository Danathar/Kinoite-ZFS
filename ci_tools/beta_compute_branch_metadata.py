from __future__ import annotations

import re

from ci_tools.common import require_env, write_github_outputs


UNSAFE_CHARS_RE = re.compile(r"[^a-z0-9._-]+")
MAX_LENGTH = 120


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


def build_branch_metadata(branch_name: str) -> tuple[str, str]:
    # Generate branch-specific names so test builds do not overwrite main artifacts.
    safe_branch = sanitize_branch_name(branch_name)
    image_tag = clamp_tag(f"beta-{safe_branch}", "beta-branch")
    akmods_repo = clamp_tag(f"akmods-zfs-{safe_branch}", "akmods-zfs-branch")
    return image_tag, akmods_repo


def main() -> None:
    # GitHub sets this to the branch name that triggered the run.
    branch_name = require_env("GITHUB_REF_NAME")
    image_tag, akmods_repo = build_branch_metadata(branch_name)

    write_github_outputs({"image_tag": image_tag, "akmods_repo": akmods_repo})
    print(f"Branch image tag: {image_tag}")
    print(f"Branch akmods repo: {akmods_repo}")


if __name__ == "__main__":
    main()
