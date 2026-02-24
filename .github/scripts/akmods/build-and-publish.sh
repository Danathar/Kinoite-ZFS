#!/usr/bin/env bash
set -euo pipefail

cd /tmp/akmods
just build
just login
just push
just manifest
