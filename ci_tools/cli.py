from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping

from ci_tools.common import CiToolError


def command_map() -> dict[str, Callable[[], None]]:
    """
    Map CLI command names to Python entry functions.

    Each value is a `main()` function from one workflow helper module.
    """
    from ci_tools.akmods_build_and_publish import main as akmods_build_and_publish
    from ci_tools.akmods_clone_pinned import main as akmods_clone_pinned
    from ci_tools.akmods_configure_zfs_target import main as akmods_configure_zfs_target
    from ci_tools.beta_check_branch_akmods_cache import main as beta_check_branch_akmods_cache
    from ci_tools.beta_compute_branch_metadata import main as beta_compute_branch_metadata
    from ci_tools.beta_configure_branch_recipe import main as beta_configure_branch_recipe
    from ci_tools.beta_detect_fedora_version import main as beta_detect_fedora_version
    from ci_tools.beta_publish_branch_akmods_alias import main as beta_publish_branch_akmods_alias
    from ci_tools.main_check_candidate_akmods_cache import main as main_check_candidate_akmods_cache
    from ci_tools.main_configure_candidate_recipe import main as main_configure_candidate_recipe
    from ci_tools.main_publish_candidate_akmods_alias import (
        main as main_publish_candidate_akmods_alias,
    )
    from ci_tools.main_promote_stable import main as main_promote_stable
    from ci_tools.main_resolve_build_inputs import main as main_resolve_build_inputs
    from ci_tools.main_write_build_inputs_manifest import main as main_write_build_inputs_manifest

    return {
        "main-resolve-build-inputs": main_resolve_build_inputs,
        "main-write-build-inputs-manifest": main_write_build_inputs_manifest,
        "main-check-candidate-akmods-cache": main_check_candidate_akmods_cache,
        "main-configure-candidate-recipe": main_configure_candidate_recipe,
        "main-publish-candidate-akmods-alias": main_publish_candidate_akmods_alias,
        "main-promote-stable": main_promote_stable,
        "beta-compute-branch-metadata": beta_compute_branch_metadata,
        "beta-detect-fedora-version": beta_detect_fedora_version,
        "beta-check-branch-akmods-cache": beta_check_branch_akmods_cache,
        "beta-configure-branch-recipe": beta_configure_branch_recipe,
        "beta-publish-branch-akmods-alias": beta_publish_branch_akmods_alias,
        "akmods-clone-pinned": akmods_clone_pinned,
        "akmods-configure-zfs-target": akmods_configure_zfs_target,
        "akmods-build-and-publish": akmods_build_and_publish,
    }


def build_parser(commands: Mapping[str, Callable[[], None]]) -> argparse.ArgumentParser:
    """Build argument parser with one positional command choice."""
    parser = argparse.ArgumentParser(
        prog="python3 -m ci_tools.cli",
        description="Run one workflow helper command.",
    )
    parser.add_argument("command", choices=sorted(commands.keys()))
    return parser


def run_command(command: str, commands: Mapping[str, Callable[[], None]]) -> None:
    """
    Run one registered command.

    `commands` is passed in to keep this function easy to test.
    """
    commands[command]()


def main(argv: list[str] | None = None) -> None:
    # Build command registry once so parser and dispatcher use the same keys.
    commands = command_map()
    parser = build_parser(commands)
    args = parser.parse_args(argv)

    try:
        run_command(args.command, commands)
    except CiToolError as exc:
        # Keep failures short and readable in workflow logs.
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
