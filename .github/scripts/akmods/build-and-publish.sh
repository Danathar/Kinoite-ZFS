#!/usr/bin/env bash
# Script: akmods/build-and-publish.sh
# What: Executes the upstream akmods build/publish lifecycle from a prepared /tmp/akmods checkout.
# Doing: Runs `just build`, `just login`, `just push`, and `just manifest` in order.
# Why: Centralizes akmods publish behavior so workflows stay orchestration-focused and deterministic.
# Goal: Produce and publish the ZFS akmods cache image/manifest for the current pipeline context.
set -euo pipefail

# Upstream akmods tooling expects to run from its repository root in /tmp/akmods.
cd /tmp/akmods

# Build target RPMs/images for the configured akmods target (zfs in our workflows).
just build
# Authenticate to GHCR using credentials exported by the workflow step env.
just login
# Push per-arch image layers for the configured akmods cache repository/tag.
just push
# Publish/update the multi-arch manifest list after pushing image layers.
just manifest
