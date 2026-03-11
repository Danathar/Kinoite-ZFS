"""
Script: ci_tools/main_sign_promoted_stable.py
What: Signs and verifies the promoted stable image digest after candidate-to-stable copy.
Doing: Resolves the stable `latest` digest, signs that digest in the stable repository path, then verifies the uploaded signature.
Why: Cosign signatures live under one repository path, so copying a candidate image into `kinoite-zfs:latest` does not automatically make the stable path signed.
Goal: Keep signature-required host rebases working without leaving long bash logic in the workflow YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ci_tools.common import CiToolError, normalize_owner, require_env, run_cmd, skopeo_inspect_digest


def stable_image_tag_ref(image_org: str, image_name: str) -> str:
    """Return the registry ref used to resolve the current stable `latest` digest."""

    return f"docker://ghcr.io/{image_org}/{image_name}:latest"


def stable_image_digest_ref(image_org: str, image_name: str, digest: str) -> str:
    """Return the digest-pinned stable image ref used for signing and verification."""

    return f"ghcr.io/{image_org}/{image_name}@{digest}"


def sign_promoted_stable(
    *,
    image_org: str,
    image_name: str,
    registry_actor: str,
    registry_token: str,
    cosign_private_key: str,
    digest_lookup: Callable[[str], str] = skopeo_inspect_digest,
    command_runner: Callable[..., str] = run_cmd,
) -> str:
    """
    Sign and verify the promoted stable digest, then return the digest-pinned ref.

    `digest_lookup` and `command_runner` are injectable so unit tests can prove
    the control flow without requiring live registry access or a real signing key.
    """

    if not cosign_private_key:
        raise CiToolError("SIGNING_SECRET is empty; cannot sign promoted stable image.")

    if not Path("cosign.pub").exists():
        raise CiToolError("Missing required verification key file: cosign.pub")

    stable_tag_ref = stable_image_tag_ref(image_org, image_name)
    stable_digest = digest_lookup(stable_tag_ref)
    if not stable_digest or stable_digest == "null":
        raise CiToolError(f"Failed to resolve digest for {stable_tag_ref}")

    stable_ref = stable_image_digest_ref(image_org, image_name, stable_digest)
    registry_args = [
        "--registry-username",
        registry_actor,
        "--registry-password",
        registry_token,
    ]

    command_runner(
        [
            "cosign",
            "sign",
            "--yes",
            "--key",
            "env://COSIGN_PRIVATE_KEY",
            *registry_args,
            stable_ref,
        ],
        capture_output=False,
        env={
            "COSIGN_PASSWORD": "",
            "COSIGN_PRIVATE_KEY": cosign_private_key,
        },
    )

    # Verify immediately so the workflow fails if signature upload or lookup
    # did not work from the stable repository path.
    command_runner(
        [
            "cosign",
            "verify",
            "--key",
            "cosign.pub",
            *registry_args,
            stable_ref,
        ]
    )

    print(f"Signed promoted stable digest: {stable_ref}")
    return stable_ref


def main() -> None:
    # Normalize owner means: convert to lowercase for consistent GHCR paths.
    image_org = normalize_owner(require_env("IMAGE_ORG"))
    image_name = require_env("IMAGE_NAME")
    registry_actor = require_env("REGISTRY_ACTOR")
    registry_token = require_env("REGISTRY_TOKEN")
    cosign_private_key = require_env("COSIGN_PRIVATE_KEY")

    sign_promoted_stable(
        image_org=image_org,
        image_name=image_name,
        registry_actor=registry_actor,
        registry_token=registry_token,
        cosign_private_key=cosign_private_key,
    )


if __name__ == "__main__":
    main()
