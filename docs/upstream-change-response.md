# Upstream Change Response Guide

If a term is unfamiliar, check the shared glossary first:
[`docs/glossary.md`](./glossary.md)

## Purpose

Use this guide when a build fails because something upstream changed (Fedora kernel, Kinoite base image, build container, ZFS compatibility, or registry behavior).

This document is for operators and users who need to answer two questions quickly:

1. Is stable still safe to use?
2. What exact action should we take next?

## Scope

This guide covers failures in:

1. `Build And Promote Main Image` ([`.github/workflows/build.yml`](../.github/workflows/build.yml))
2. Candidate akmods build
3. Candidate image build
4. Promotion to stable tags
5. Replay/lock mode execution

## Fast Triage (First 10 Minutes)

1. Identify the failing run and failing job.
2. Confirm whether stable tags were changed.
3. Determine whether failure is candidate-only or promotion-related.
4. Choose the matching recovery action in this document.

## Step 1: Identify What Failed

Run:

```bash
# List recent workflow runs.
gh run list --limit 20 --json databaseId,workflowName,event,status,conclusion,displayTitle,createdAt
```

For the specific run:

```bash
# Show status, result, and jobs for one run.
gh run view <RUN_ID> --json status,conclusion,event,jobs,url --jq '.'
```

If you need full logs:

```bash
# Download combined logs for a run.
gh run view <RUN_ID> --log
```

## Step 2: Confirm Stable Safety

Candidate failure should not move stable tags. Verify directly:

```bash
# Check stable image digest and kernel label.
skopeo inspect docker://ghcr.io/danathar/kinoite-zfs:latest | jq -r '.Digest,.Labels["ostree.linux"]'
# Check stable akmods digest.
skopeo inspect docker://ghcr.io/danathar/akmods-zfs:main-43 | jq -r '.Digest'
```

Compare these values with the last known good promotion run.

If promotion was skipped, stable is intentionally unchanged.

## Step 3: Pull Build Input Manifest

Each main run uploads a `build-inputs-<run_id>` artifact.

Download and inspect:

```bash
# Download the build-inputs file from this run.
gh run download <RUN_ID> -n build-inputs-<RUN_ID> -D /tmp/build-inputs-<RUN_ID>
# Pretty-print the JSON file.
jq . /tmp/build-inputs-<RUN_ID>/build-inputs.json
```

Check these fields first:

1. `inputs.base_image_pinned`
2. `inputs.base_image_tag`
3. `inputs.kernel_release`
4. `inputs.build_container_pinned`
5. `inputs.zfs_minor_version`
6. `inputs.akmods_upstream_ref`
7. `inputs.use_input_lock`

## Failure Patterns And Actions

### Pattern A: Candidate Akmods Build Fails

Typical signal:

1. `Build Self-Hosted ZFS Akmods (candidate)` fails.
2. Errors mention OpenZFS build/compile, missing symbols, kernel incompatibility, or source packaging changes.

Likely cause:

1. Fedora kernel advanced faster than current ZFS compatibility.
2. Upstream packaging/build assumptions changed.

Action:

1. Do not force promotion.
2. Keep stable on last successful promotion.
3. Run candidate-only tests (`promote_to_stable=false`) until compatibility is restored.
4. If needed, replay last known-good locked inputs for deterministic troubleshooting.

### Pattern B: Candidate Image Build Fails (Akmods Succeeded)

Typical signal:

1. `Build Candidate Image` fails.
2. Errors mention missing `zfs.ko`, `rpm-ostree install`, or kernel/module mismatch checks.

Likely cause:

1. Candidate akmods cache does not match candidate kernel as expected.
2. Recipe-side validation caught a stale or mismatched module set.

Action:

1. Re-run candidate with `rebuild_akmods=true`.
2. Verify candidate compose pins `image-version` to the resolved immutable base tag from `build-inputs.json`.
3. Verify candidate compose references candidate akmods `AKMODS_IMAGE` tag `ghcr.io/<owner>/akmods-zfs-candidate:main-<fedora>-<kernel_release>`.
4. Verify akmods logs show `Pinned akmods kernel release to <kernel_release>`.
5. Keep promotion disabled until candidate passes.

### Pattern C: Promotion Job Fails

Typical signal:

1. Candidate jobs pass.
2. `Promote Candidate To Stable` fails.

Likely cause:

1. Registry transient issue, auth issue, or partial copy failure.
2. Candidate akmods tag missing for that Fedora version (`akmods-zfs-candidate:main-<fedora>`).
3. Stable digest signing failed after promotion copy (for example missing signing secret or signature upload failure).

Action:

1. Verify current stable tags before retrying.
2. Re-run workflow in lock mode with same inputs and `promote_to_stable=true`.
3. Confirm both stable image and stable akmods tags are updated together.
4. Confirm stable digest has a valid signature:

```bash
DIGEST=$(skopeo inspect docker://ghcr.io/danathar/kinoite-zfs:latest | jq -r .Digest)
cosign verify --key cosign.pub ghcr.io/danathar/kinoite-zfs@"$DIGEST"
```

### Pattern D: Replay Mode Fails

Typical signal:

1. `Resolve build inputs` fails.
2. Messages mention lock file path, field mismatch, or build container mismatch.

Likely cause:

1. [`ci/inputs.lock.json`](../ci/inputs.lock.json) missing/invalid or inconsistent with manual dispatch inputs.

Action:

1. Ensure [`ci/inputs.lock.json`](../ci/inputs.lock.json) exists in the branch being run.
2. Use `build_container_image` exactly equal to lock file `build_container`.
3. Verify lock fields are non-empty and not placeholder values.

### Pattern E: Upstream Floating Inputs Changed Behavior

Typical signal:

1. Same repo commit behaves differently across two runs.

Likely cause:

1. Floating refs changed (`kinoite-main:latest`, builder image tag drift, registry changes).

Action:

1. Compare `build-inputs.json` from both runs.
2. Reproduce with lock replay on the known-good input set.
3. Only promote when candidate succeeds on intended inputs.

## Safe Operational Defaults

1. Treat `latest` as production/stable.
2. Treat `candidate` as test/pre-promotion.
3. Use `promote_to_stable=false` for experiments and incident analysis.
4. Use `use_input_lock=true` for deterministic replay.
5. Re-enable promotion only after candidate is green.

## Production Recovery Procedure

1. Identify last successful promotion run.
2. Confirm stable tags still point to that run.
3. Freeze updates on consumer systems if required.
4. Continue candidate validation runs until green.
5. Promote only after successful candidate run with expected inputs.

## Host Verification After Recovery

After rebasing to stable and rebooting:

```bash
uname -r
rpm -q kmod-zfs
sudo modprobe zfs
zpool --version
zfs --version
find /lib/modules/$(uname -r) -maxdepth 4 -type f -name 'zfs.ko*'
```

If creating test pools on atomic hosts, use `/var` mountpoints.

## Data To Collect For Escalation

When opening an issue or documenting an incident, capture:

1. Run URL and run ID.
2. Failing job name and failing step.
3. `build-inputs.json` from failing run.
4. `build-inputs.json` from last successful run.
5. Exact error excerpt from logs.
6. Current digests for stable image and stable akmods tags.

## Related Documents

1. High-level architecture: [`docs/architecture-overview.md`](./architecture-overview.md)
2. Detailed technical runbook and issue log: [`docs/zfs-kinoite-testing.md`](./zfs-kinoite-testing.md)
