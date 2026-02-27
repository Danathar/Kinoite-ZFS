# Akmods Fork Maintenance

## Purpose

This repository no longer patches `ublue-os/akmods` scripts at runtime during CI.

Instead, we pin CI to a maintained fork commit and update that pin only after validation.
This keeps builds deterministic and removes fragile in-run `sed`/`perl` patch logic.

## Current Source Of Truth

1. Fork repository: `https://github.com/Danathar/akmods`
2. Pinned commit in this repo:
   - [`.github/workflows/build.yml`](../.github/workflows/build.yml) (`AKMODS_UPSTREAM_REF`)
   - [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml) (`AKMODS_UPSTREAM_REF`)
3. Fork commit currently expected by this repo:
   - `9d13b6950811cdaae2e8ab748c85c5da35810ae3`

## What Is Customized In The Fork

1. `build_files/zfs/build-kmod-zfs.sh`
   - Installs `jq` before querying OpenZFS release metadata.
2. `build_files/prep/build-prep.sh`
   - Includes `python3-cffi` in the common build dependency set.

These two changes replaced prior runtime patching in this repo's workflows.

## Standard Update Procedure

1. Sync local fork clone and upstream:

```bash
git clone https://github.com/Danathar/akmods.git
cd akmods
git remote add upstream https://github.com/ublue-os/akmods.git
git fetch upstream
```

2. Create/update working branch for refresh:

```bash
git checkout -B kinoite-zfs-refresh upstream/main
```

3. Reapply/port required fork changes (`jq`, `python3-cffi`, and any approved local fixes), then commit:

```bash
git add build_files/zfs/build-kmod-zfs.sh build_files/prep/build-prep.sh
git commit -m "zfs: refresh fork patches for kinoite-zfs pipeline"
```

4. Push updated fork branch (or `main`, if that is your chosen policy):

```bash
git push origin HEAD:main
```

5. Capture the new fork commit SHA:

```bash
git rev-parse HEAD
```

6. In `Kinoite-ZFS`, update both workflow pins to that SHA:
   - [`.github/workflows/build.yml`](../.github/workflows/build.yml)
   - [`.github/workflows/build-beta.yml`](../.github/workflows/build-beta.yml)

7. Validate in `Kinoite-ZFS` before promotion:
   - Run `Build And Promote Main Image` with:
     - `rebuild_akmods=true`
     - `promote_to_stable=false`
   - Rebase a VM to the produced image and run runtime ZFS checks.

8. After validation, run promotion (`promote_to_stable=true`) and then merge.

## Rollback Procedure

If a new fork pin breaks builds:

1. Revert `AKMODS_UPSTREAM_REF` in both workflows to the previous known-good SHA.
2. Re-run pipeline with `rebuild_akmods=true`.
3. Confirm candidate and promotion recover.

## Operator Notes

1. Keep fork updates small and purpose-specific.
2. Prefer upstreaming stable fixes to `ublue-os/akmods` when possible.
3. Treat this fork as controlled infrastructure, not a fast-moving feature branch.
