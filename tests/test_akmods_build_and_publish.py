"""
Script: tests/test_akmods_build_and_publish.py
What: Tests helper functions used by `ci_tools/akmods_build_and_publish.py`.
Doing: Checks kernel-name mapping and generated kernel-cache metadata values.
Why: Catches behavior changes that could break akmods build metadata.
Goal: Keep akmods helper behavior stable over time.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

from ci_tools import akmods_build_and_publish as script
from ci_tools.common import (
    AKMODS_CACHE_KERNEL_RELEASES_LABEL,
    AKMODS_CACHE_METADATA_VERSION,
    AKMODS_CACHE_METADATA_VERSION_LABEL,
)
from ci_tools.akmods_build_and_publish import (
    build_kernel_cache_document,
    kernel_major_minor_patch,
    kernel_name_for_flavor,
    manifest_tag_for_kernel_release,
    merged_cache_missing_kernel_releases,
    render_shared_cache_containerfile,
)


class AkmodsBuildAndPublishTests(unittest.TestCase):
    def test_kernel_name_for_longterm_flavor(self) -> None:
        self.assertEqual(kernel_name_for_flavor("longterm"), "kernel-longterm")
        self.assertEqual(kernel_name_for_flavor("longterm-lts"), "kernel-longterm")

    def test_kernel_name_for_standard_flavor(self) -> None:
        self.assertEqual(kernel_name_for_flavor("main"), "kernel")

    def test_kernel_major_minor_patch(self) -> None:
        value = kernel_major_minor_patch("6.18.12-200.fc43.x86_64")
        self.assertEqual(value, "6.18.12-200")

    def test_manifest_tag_for_kernel_release_strips_arch_suffix(self) -> None:
        value = manifest_tag_for_kernel_release(
            kernel_flavor="main",
            akmods_version="43",
            kernel_release="6.19.6-200.fc43.x86_64",
        )
        self.assertEqual(value, "main-43-6.19.6-200.fc43")

    def test_build_kernel_cache_document_default_path(self) -> None:
        payload, cache_path, upstream_build_root = build_kernel_cache_document(
            kernel_release="6.18.12-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="",
            shared_cache_path=True,
        )

        self.assertEqual(payload["kernel_name"], "kernel")
        self.assertEqual(payload["kernel_major_minor_patch"], "6.18.12-200")
        self.assertEqual(str(upstream_build_root), "/tmp/akmods/build")
        self.assertTrue(payload["KCWD"].endswith("/main-43/KCWD"))
        self.assertTrue(payload["KCPATH"].endswith("/main-43/KCWD/rpms"))
        self.assertTrue(str(cache_path).endswith("/main-43/KCWD/rpms/cache.json"))

    def test_build_kernel_cache_document_with_kcpath_override(self) -> None:
        payload, cache_path, upstream_build_root = build_kernel_cache_document(
            kernel_release="6.18.12-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="/custom/rpms",
            shared_cache_path=True,
        )

        self.assertEqual(str(upstream_build_root), "/tmp/akmods/build")
        self.assertEqual(payload["KCPATH"], "/custom/rpms")
        self.assertEqual(str(cache_path), "/custom/rpms/cache.json")

    def test_build_kernel_cache_document_isolates_multi_kernel_paths(self) -> None:
        first_payload, first_cache_path, first_build_root = build_kernel_cache_document(
            kernel_release="6.18.12-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="",
            shared_cache_path=False,
        )
        second_payload, second_cache_path, second_build_root = build_kernel_cache_document(
            kernel_release="6.18.16-200.fc43.x86_64",
            kernel_flavor="main",
            akmods_version="43",
            build_root=Path("/tmp/akmods/build"),
            kcpath_override="",
            shared_cache_path=False,
        )

        # Multi-kernel rebuilds keep one cache tree per kernel so upstream
        # akmods tooling never sees mixed kernel RPMs in the same directory.
        self.assertNotEqual(first_build_root, second_build_root)
        self.assertNotEqual(first_payload["KCPATH"], second_payload["KCPATH"])
        self.assertNotEqual(first_cache_path, second_cache_path)

    def test_merged_cache_missing_kernel_releases_reports_missing_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            merged_root = Path(temp_dir)
            rpm_dir = merged_root / "rpms" / "kmods" / "zfs"
            rpm_dir.mkdir(parents=True, exist_ok=True)
            (rpm_dir / "kmod-zfs-6.18.13-200.fc43.x86_64-2.4.1-1.fc43.x86_64.rpm").touch()

            missing = merged_cache_missing_kernel_releases(
                merged_root=merged_root,
                kernel_releases=[
                    "6.18.13-200.fc43.x86_64",
                    "6.18.16-200.fc43.x86_64",
                ],
            )

        self.assertEqual(missing, ["6.18.16-200.fc43.x86_64"])

    def test_render_shared_cache_containerfile_includes_kernel_metadata_labels(self) -> None:
        containerfile = render_shared_cache_containerfile(
            kernel_releases=[
                "6.18.16-200.fc43.x86_64",
                "6.18.13-200.fc43.x86_64",
            ]
        )

        self.assertIn(
            f'LABEL {AKMODS_CACHE_METADATA_VERSION_LABEL}="{AKMODS_CACHE_METADATA_VERSION}"',
            containerfile,
        )
        self.assertIn(
            (
                f'LABEL {AKMODS_CACHE_KERNEL_RELEASES_LABEL}='
                '"6.18.13-200.fc43.x86_64 6.18.16-200.fc43.x86_64"'
            ),
            containerfile,
        )
        self.assertTrue(containerfile.endswith("COPY rpms /rpms\n"))

    def test_write_kernel_cache_file_exports_isolated_upstream_build_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(script, "AKMODS_WORKTREE", Path(tempdir)):
                with patch.dict(
                    script.os.environ,
                    {
                        "AKMODS_KERNEL": "main",
                        "AKMODS_VERSION": "43",
                    },
                    clear=True,
                ):
                    script.write_kernel_cache_file(
                        kernel_release="6.18.16-200.fc43.x86_64",
                        shared_cache_path=False,
                    )

                    self.assertTrue(
                        script.os.environ["AKMODS_BUILDDIR"].endswith(
                            "/build/6.18.16-200.fc43.x86_64"
                        )
                    )
                    self.assertFalse("KCPATH" in script.os.environ)

    def test_write_kernel_cache_file_rejects_fixed_kcpath_in_multi_kernel_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(script, "AKMODS_WORKTREE", Path(tempdir)):
                with patch.dict(
                    script.os.environ,
                    {
                        "AKMODS_KERNEL": "main",
                        "AKMODS_VERSION": "43",
                        "KCPATH": "/tmp/shared-rpms",
                    },
                    clear=True,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "cannot reuse a fixed KCPATH override",
                    ):
                        script.write_kernel_cache_file(
                            kernel_release="6.18.16-200.fc43.x86_64",
                            shared_cache_path=False,
                        )

    def test_main_single_kernel_builds_kernel_then_merges_shared_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(script, "AKMODS_WORKTREE", Path(tempdir)):
                with patch.object(
                    script,
                    "kernel_releases_from_env",
                    return_value=["6.18.16-200.fc43.x86_64"],
                ):
                    with patch.object(script, "build_and_push_kernel_release") as build_release:
                        with patch.object(
                            script,
                            "merge_and_push_shared_cache_image",
                        ) as merge_shared:
                            with patch.object(script, "run_cmd") as run_cmd:
                                with patch.dict(script.os.environ, {}, clear=False):
                                    script.main()
                                    self.assertEqual(script.os.environ["BUILDAH_LAYERS"], "false")

        build_release.assert_called_once_with(
            "6.18.16-200.fc43.x86_64",
            shared_cache_path=False,
        )
        merge_shared.assert_called_once_with(
            kernel_releases=["6.18.16-200.fc43.x86_64"]
        )
        self.assertEqual(
            run_cmd.call_args_list,
            [
                call(["just", "login"], cwd=str(Path(tempdir)), capture_output=False),
            ],
        )

    def test_main_without_kernel_releases_keeps_upstream_manifest_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(script, "AKMODS_WORKTREE", Path(tempdir)):
                with patch.object(script, "kernel_releases_from_env", return_value=[]):
                    with patch.object(script, "clear_local_manifest_targets") as clear_targets:
                        with patch.object(script, "run_cmd") as run_cmd:
                            with patch.dict(
                                script.os.environ,
                                {"KERNEL_RELEASE": "6.18.16-200.fc43.x86_64"},
                                clear=False,
                            ):
                                script.main()

        clear_targets.assert_called_once_with(kernel_release="6.18.16-200.fc43.x86_64")
        self.assertEqual(
            run_cmd.call_args_list,
            [
                call(["just", "build"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "login"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "push"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "manifest"], cwd=str(Path(tempdir)), capture_output=False),
            ],
        )

    def test_clear_local_manifest_targets_removes_shared_and_kernel_refs(self) -> None:
        recorded: list[list[str]] = []

        def fake_run(args: list[str], **_kwargs: object) -> object:
            recorded.append(args)

            class Result:
                returncode = 1 if args[:3] == ["podman", "manifest", "rm"] else 0

            return Result()

        with patch.dict(
            script.os.environ,
            {
                "AKMODS_KERNEL": "main",
                "AKMODS_VERSION": "43",
                "AKMODS_REPO": "kinoite-zfs-bluebuild-akmods",
                "GITHUB_REPOSITORY_OWNER": "Danathar",
            },
            clear=False,
        ):
            with patch.object(script.subprocess, "run", side_effect=fake_run):
                script.clear_local_manifest_targets(
                    kernel_release="6.19.6-200.fc43.x86_64"
                )

        self.assertEqual(
            recorded,
            [
                [
                    "podman",
                    "manifest",
                    "rm",
                    "ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
                ],
                [
                    "podman",
                    "rmi",
                    "ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43",
                ],
                [
                    "podman",
                    "manifest",
                    "rm",
                    "ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43-6.19.6-200.fc43",
                ],
                [
                    "podman",
                    "rmi",
                    "ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43-6.19.6-200.fc43",
                ],
            ],
        )

    def test_merge_and_push_shared_cache_image_builds_shared_tags(self) -> None:
        kernel_releases = [
            "6.18.13-200.fc43.x86_64",
            "6.18.16-200.fc43.x86_64",
        ]

        unpack_index = {"value": 0}

        def fake_unpack(_layer_files: list[Path], destination: Path) -> None:
            kernel_release = kernel_releases[unpack_index["value"]]
            unpack_index["value"] += 1

            # The merge helper republishes the same directory layout that the
            # cache-check step later inspects inside the shared image.
            rpm_dir = destination / "rpms" / "kmods" / "zfs"
            rpm_dir.mkdir(parents=True, exist_ok=True)
            (destination / "kernel-rpms").mkdir(parents=True, exist_ok=True)
            (
                rpm_dir / f"kmod-zfs-{kernel_release}-2.4.1-1.fc43.x86_64.rpm"
            ).touch()

        def fake_run_cmd(args: list[str], **_kwargs: object) -> str:
            if args == ["uname", "-m"]:
                return "x86_64\n"
            return ""

        with patch.dict(
            script.os.environ,
            {
                "AKMODS_KERNEL": "main",
                "AKMODS_VERSION": "43",
                "AKMODS_REPO": "akmods-zfs",
                "GITHUB_REPOSITORY_OWNER": "Danathar",
            },
            clear=False,
        ):
            with patch.object(script, "skopeo_copy") as skopeo_copy:
                with patch.object(
                    script,
                    "load_layer_files_from_oci_layout",
                    return_value=[Path("layer.tar")],
                ):
                    with patch.object(script, "unpack_layer_tarballs", side_effect=fake_unpack):
                        with patch.object(script, "run_cmd", side_effect=fake_run_cmd) as run_cmd:
                            script.merge_and_push_shared_cache_image(
                                kernel_releases=kernel_releases
                            )

        self.assertEqual(skopeo_copy.call_count, 2)
        self.assertEqual(run_cmd.call_args_list[0], call(["uname", "-m"]))

        build_command = run_cmd.call_args_list[1]
        self.assertEqual(build_command.args[0][:5], ["podman", "build", "-f", build_command.args[0][3], "-t"])
        self.assertIn("localhost/akmods-zfs:main-43", build_command.args[0])
        self.assertIn("localhost/akmods-zfs:main-43-x86_64", build_command.args[0])

        self.assertEqual(
            run_cmd.call_args_list[2],
            call(
                [
                    "podman",
                    "push",
                    "localhost/akmods-zfs:main-43-x86_64",
                    "docker://ghcr.io/danathar/akmods-zfs:main-43-x86_64",
                ],
                capture_output=False,
            ),
        )
        self.assertEqual(
            run_cmd.call_args_list[3],
            call(
                [
                    "podman",
                    "push",
                    "localhost/akmods-zfs:main-43",
                    "docker://ghcr.io/danathar/akmods-zfs:main-43",
                ],
                capture_output=False,
            ),
        )

    def test_main_builds_each_kernel_then_merges_shared_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            with patch.object(script, "AKMODS_WORKTREE", Path(tempdir)):
                with patch.object(
                    script,
                    "kernel_releases_from_env",
                    return_value=[
                        "6.18.13-200.fc43.x86_64",
                        "6.18.16-200.fc43.x86_64",
                    ],
                ):
                    with patch.object(script, "write_kernel_cache_file") as write_cache:
                        with patch.object(script, "merge_and_push_shared_cache_image") as merge_shared:
                            with patch.object(script, "run_cmd") as run_cmd:
                                with patch.dict(script.os.environ, {}, clear=False):
                                    script.main()
                                    self.assertEqual(script.os.environ["BUILDAH_LAYERS"], "false")

        self.assertEqual(
            write_cache.call_args_list,
            [
                call(
                    kernel_release="6.18.13-200.fc43.x86_64",
                    shared_cache_path=False,
                ),
                call(
                    kernel_release="6.18.16-200.fc43.x86_64",
                    shared_cache_path=False,
                ),
            ],
        )
        self.assertEqual(
            run_cmd.call_args_list,
            [
                call(["just", "login"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "build"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "push"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "build"], cwd=str(Path(tempdir)), capture_output=False),
                call(["just", "push"], cwd=str(Path(tempdir)), capture_output=False),
            ],
        )
        merge_shared.assert_called_once_with(
            kernel_releases=[
                "6.18.13-200.fc43.x86_64",
                "6.18.16-200.fc43.x86_64",
            ]
        )


if __name__ == "__main__":
    unittest.main()
