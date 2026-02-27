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


def build_branch_metadata(branch_name: str) -> str:
    # Return one branch-scoped tag prefix in the shared candidate cache repo.
    # Branch compose uses this prefix (`br-<branch>`) so test runs stay isolated.
    safe_branch = sanitize_branch_name(branch_name)
    akmods_public_tag_prefix = clamp_tag(f"br-{safe_branch}", "br-branch")
    return akmods_public_tag_prefix


def main() -> None:
    # GitHub sets this to the branch name that triggered the run.
    branch_name = require_env("GITHUB_REF_NAME")
    akmods_public_tag_prefix = build_branch_metadata(branch_name)

    # Export values so downstream jobs can reference them.
    write_github_outputs(
        {
            "akmods_public_tag_prefix": akmods_public_tag_prefix,
        }
    )
    print(f"Branch public akmods tag prefix: {akmods_public_tag_prefix}")


if __name__ == "__main__":
    main()
