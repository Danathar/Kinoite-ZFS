#!/usr/bin/env bash
# Thin wrapper: call the shared Python CLI entrypoint.
set -euo pipefail
exec python3 -m ci_tools.cli beta-check-branch-akmods-cache
