"""
Script: ci_tools/main_write_build_provenance.py
What: Writes a success-path provenance record for main workflow runs.
Doing: Resolves candidate and optional stable image/akmods digests, combines them with the pinned build inputs, and writes `artifacts/build-provenance.json`.
Why: Successful runs should leave behind one compact record that supports rollback, replay, and incident review.
Goal: Persist high-signal artifact provenance for each successful main build.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ci_tools.common import normalize_owner, require_env, skopeo_inspect_digest


ARTIFACT_DIR = Path("artifacts")
ARTIFACT_PATH = ARTIFACT_DIR / "build-provenance.json"


def image_tag_ref(*, image_org: str, image_name: str, tag: str) -> str:
    """Return one GHCR tag ref without a transport prefix."""

    return f"ghcr.io/{image_org}/{image_name}:{tag}"


def image_digest_ref(*, image_org: str, image_name: str, digest: str) -> str:
    """Return one GHCR digest ref without a transport prefix."""

    return f"ghcr.io/{image_org}/{image_name}@{digest}"


def _document_ref_and_digest(
    *,
    image_org: str,
    image_name: str,
    tag: str,
    digest: str,
) -> dict[str, str]:
    """Return a small ref bundle for one image tag/digest pair."""

    return {
        "tag": tag,
        "tag_ref": image_tag_ref(
            image_org=image_org,
            image_name=image_name,
            tag=tag,
        ),
        "digest": digest,
        "digest_ref": image_digest_ref(
            image_org=image_org,
            image_name=image_name,
            digest=digest,
        ),
    }


def build_provenance_document(
    *,
    image_org: str,
    fedora_version: str,
    image_name: str,
    candidate_image_name: str,
    stable_akmods_repo: str,
    candidate_akmods_repo: str,
    kernel_releases: list[str],
    base_image_ref: str,
    base_image_name: str,
    base_image_tag: str,
    base_image_pinned: str,
    base_image_digest: str,
    build_container_ref: str,
    build_container_pinned: str,
    build_container_digest: str,
    zfs_minor_version: str,
    akmods_upstream_ref: str,
    promotion_result: str,
    registry_creds: str,
    candidate_image_digest: str,
    digest_lookup=skopeo_inspect_digest,
) -> dict[str, object]:
    """Build the JSON provenance document for one successful main run."""

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sha_short = require_env("GITHUB_SHA")[:7]
    run_number = require_env("GITHUB_RUN_NUMBER")
    candidate_image_tag = f"{sha_short}-{fedora_version}"
    candidate_akmods_tag = f"main-{fedora_version}"
    candidate_akmods_ref = image_tag_ref(
        image_org=image_org,
        image_name=candidate_akmods_repo,
        tag=candidate_akmods_tag,
    )
    candidate_akmods_digest = digest_lookup(
        f"docker://{candidate_akmods_ref}",
        creds=registry_creds,
    )

    document: dict[str, object] = {
        "schema_version": 1,
        "generated_at": generated_at,
        "repository": require_env("GITHUB_REPOSITORY"),
        "workflow": require_env("GITHUB_WORKFLOW"),
        "run": {
            "id": int(require_env("GITHUB_RUN_ID")),
            "attempt": int(require_env("GITHUB_RUN_ATTEMPT")),
            "number": int(run_number),
            "ref": require_env("GITHUB_REF"),
            "sha": require_env("GITHUB_SHA"),
            "actor": require_env("GITHUB_ACTOR"),
        },
        "inputs": {
            "fedora_version": fedora_version,
            "kernel_releases": kernel_releases,
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
        },
        "candidate": {
            "image": _document_ref_and_digest(
                image_org=image_org,
                image_name=candidate_image_name,
                tag=candidate_image_tag,
                digest=candidate_image_digest,
            ),
            "akmods": _document_ref_and_digest(
                image_org=image_org,
                image_name=candidate_akmods_repo,
                tag=candidate_akmods_tag,
                digest=candidate_akmods_digest,
            ),
        },
        "stable": {
            "promotion_result": promotion_result,
            "promoted": promotion_result == "success",
        },
    }

    if promotion_result == "success":
        stable_image_tag = "latest"
        stable_image_digest = digest_lookup(
            f"docker://{image_tag_ref(image_org=image_org, image_name=image_name, tag=stable_image_tag)}",
            creds=registry_creds,
        )
        stable_akmods_digest = digest_lookup(
            f"docker://{image_tag_ref(image_org=image_org, image_name=stable_akmods_repo, tag=candidate_akmods_tag)}",
            creds=registry_creds,
        )
        document["stable"] = {
            "promotion_result": promotion_result,
            "promoted": True,
            "audit_tag": f"stable-{run_number}-{sha_short}",
            "image": _document_ref_and_digest(
                image_org=image_org,
                image_name=image_name,
                tag=stable_image_tag,
                digest=stable_image_digest,
            ),
            "akmods": _document_ref_and_digest(
                image_org=image_org,
                image_name=stable_akmods_repo,
                tag=candidate_akmods_tag,
                digest=stable_akmods_digest,
            ),
        }

    return document


def main() -> None:
    image_org = normalize_owner(require_env("GITHUB_REPOSITORY_OWNER"))
    fedora_version = require_env("FEDORA_VERSION")
    image_name = require_env("IMAGE_NAME")
    candidate_image_name = require_env("CANDIDATE_IMAGE_NAME")
    stable_akmods_repo = require_env("STABLE_AKMODS_REPO")
    candidate_akmods_repo = require_env("CANDIDATE_AKMODS_REPO")
    kernel_releases = require_env("KERNEL_RELEASES").split()
    base_image_ref = require_env("BASE_IMAGE_REF")
    base_image_name = require_env("BASE_IMAGE_NAME")
    base_image_tag = require_env("BASE_IMAGE_TAG")
    base_image_pinned = require_env("BASE_IMAGE_PINNED")
    base_image_digest = require_env("BASE_IMAGE_DIGEST")
    build_container_ref = require_env("BUILD_CONTAINER_REF")
    build_container_pinned = require_env("BUILD_CONTAINER_PINNED")
    build_container_digest = require_env("BUILD_CONTAINER_DIGEST")
    zfs_minor_version = require_env("ZFS_MINOR_VERSION")
    akmods_upstream_ref = require_env("AKMODS_UPSTREAM_REF")
    promotion_result = require_env("PROMOTION_RESULT")
    registry_creds = f"{require_env('REGISTRY_ACTOR')}:{require_env('REGISTRY_TOKEN')}"
    candidate_image_digest = require_env("CANDIDATE_IMAGE_DIGEST")

    document = build_provenance_document(
        image_org=image_org,
        fedora_version=fedora_version,
        image_name=image_name,
        candidate_image_name=candidate_image_name,
        stable_akmods_repo=stable_akmods_repo,
        candidate_akmods_repo=candidate_akmods_repo,
        kernel_releases=kernel_releases,
        base_image_ref=base_image_ref,
        base_image_name=base_image_name,
        base_image_tag=base_image_tag,
        base_image_pinned=base_image_pinned,
        base_image_digest=base_image_digest,
        build_container_ref=build_container_ref,
        build_container_pinned=build_container_pinned,
        build_container_digest=build_container_digest,
        zfs_minor_version=zfs_minor_version,
        akmods_upstream_ref=akmods_upstream_ref,
        promotion_result=promotion_result,
        registry_creds=registry_creds,
        candidate_image_digest=candidate_image_digest,
    )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(ARTIFACT_PATH.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    main()
