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
skopeo inspect docker://ghcr.io/danathar/kinoite-zfs-bluebuild-akmods:main-43 | jq -r '.Digest'
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
5. If the log shows `podman manifest create ... main-<fedora> ... already in use` during a multi-kernel rebuild, the failure is in manifest sequencing, not kernel-version detection.
6. If a later candidate image build reports `No ZFS module for base kernel <kernel_release>` even though akmods just published that kernel tag, inspect whether the multi-kernel akmods rebuild reused stale Buildah layers from the earlier kernel iteration.
7. Current repo-side mitigation for multi-kernel bases is: build isolated per-kernel akmods outputs first, then merge them into one shared `main-<fedora>` cache image for downstream consumers.
8. Deferred refactor option to record here for later: stop using one shared cache image and instead teach candidate/stable compose paths to consume multiple kernel-specific akmods tags directly. That is a larger design change and is intentionally not the current default.

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
3. Verify `build-inputs.json` records every kernel shipped in the base image under `inputs.kernel_releases`.
4. Verify candidate compose references candidate akmods `AKMODS_IMAGE` tag `ghcr.io/<owner>/kinoite-zfs-bluebuild-akmods-candidate:main-<fedora>`.
5. Verify akmods logs show one `Pinned akmods kernel release to <kernel_release>` line for each base-image kernel that required a cache rebuild.
6. If the cache image already contains every expected `kmod-zfs-<kernel_release>-*.rpm` file, inspect whether those RPM files share the same internal RPM identity (`rpm -qp --qf '%{NAME} %{VERSION}-%{RELEASE} %{ARCH}\n' ...`). If they do, candidate compose must install only one `kmod-zfs` package through `rpm-ostree` and unpack the remaining kernel-specific payloads directly.
7. Deferred refactor option to keep documented here for later: replace the current shared-image compatibility shim with a broader downstream design that consumes multiple kernel-specific akmods tags directly instead of one merged `main-<fedora>` tag.
8. Keep promotion disabled until candidate passes.

### Pattern C: Promotion Job Fails

Typical signal:

1. Candidate jobs pass.
2. `Promote Candidate To Stable` fails.

Likely cause:

1. Registry transient issue, auth issue, or partial copy failure.
2. Candidate akmods tag missing for that Fedora version (`kinoite-zfs-bluebuild-akmods-candidate:main-<fedora>`).
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

### Pattern F: Signed Host Switch Fails With “Signature Required, But No Signature Exists”

Typical signal:

1. `bootc switch` or signed rebase fails during image import.
2. Error text includes: `A signature was required, but no signature exists`.
3. Another common variant is: `Error parsing signature storage configuration`
   followed by `namespace ... defined both in ...`.

Likely cause:

1. Host-side trust policy cannot resolve signatures for the target repo name
   (for example stable vs candidate repository mismatch).
2. Sigstore attachment discovery config for that repo name is missing.
3. More than one file under `/etc/containers/registries.d/` declares the same
   repo namespace, so `containers/image` aborts before it can check signatures.

Action:

1. Confirm target image digest is signed in registry:

```bash
cosign verify --key cosign.pub ghcr.io/danathar/kinoite-zfs:latest
```

2. Inspect trust policy inside the target image:

```bash
podman run --rm --entrypoint cat ghcr.io/danathar/kinoite-zfs:latest /etc/containers/policy.json
podman run --rm --entrypoint sh ghcr.io/danathar/kinoite-zfs:latest -lc 'ls -1 /etc/containers/registries.d'
```

3. Verify both repo names are present in policy/registries config:
   - `ghcr.io/danathar/kinoite-zfs`
   - `ghcr.io/danathar/kinoite-zfs-candidate`

4. If migrating from a different image family, do one unverified bootstrap rebase
   first, then switch signed.
5. If the error says a namespace is defined in two files, inspect the target
   image or host for duplicate `registries.d` entries and remove the stale one:

```bash
podman run --rm --entrypoint sh ghcr.io/danathar/kinoite-zfs:latest -lc 'ls -1 /etc/containers/registries.d && printf "\n---\n"; for f in /etc/containers/registries.d/*.yaml; do echo "## $f"; cat "$f"; echo; done'
sudo ls -1 /etc/containers/registries.d
```

6. On already-booted affected hosts, removing the stale owner-prefixed duplicate
   file (for example `danathar-kinoite-zfs-candidate.yaml`) is a valid emergency
   recovery step before retrying `bootc upgrade`.
7. For a cleaner one-shot repair on hosts already booted into older repo images,
   run the checked-in helper from the repository root:

```bash
sudo ./scripts/fix-host-signing-policy.sh
```

8. Fresh stock Kinoite hosts are different: `bootc switch ghcr.io/danathar/kinoite-zfs:latest`
   should work directly because the source host does not yet carry this repo's
   stricter namespace-specific trust requirements.

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
