#!/usr/bin/env bash
# Thin wrapper: run the Python implementation for readability and testability.
set -euo pipefail
exec python3 -m ci_tools.beta_configure_branch_recipe
