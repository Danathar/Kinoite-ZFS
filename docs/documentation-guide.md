# Documentation Guide

If a term is unfamiliar, check the shared glossary first:
[`docs/glossary.md`](./glossary.md)

## Purpose

This page is a map of the documentation itself: what each document is for,
who should read it, and in what order.

## Documentation Tree

```text
README.md
docs/
  documentation-guide.md      <- this file (doc map + reading paths)
  glossary.md                 <- shared term and command definitions
  code-reading-guide.md       <- step-by-step code reading order
  architecture-overview.md    <- high-level design and flow
  upstream-change-response.md <- incident triage and recovery actions
  zfs-kinoite-testing.md      <- deep technical design + issue history
  akmods-fork-maintenance.md  <- how to maintain the pinned akmods fork
.github/scripts/
  README.md                   <- workflow step -> CLI command -> Python module map
```

## What To Read First (By Goal)

### Goal: I am new and want the big picture

1. [`README.md`](../README.md)
2. [`docs/glossary.md`](./glossary.md)
3. [`docs/architecture-overview.md`](./architecture-overview.md)

### Goal: I want to understand the code end-to-end

1. [`docs/code-reading-guide.md`](./code-reading-guide.md)
2. [`.github/scripts/README.md`](../.github/scripts/README.md)
3. [`docs/zfs-kinoite-testing.md`](./zfs-kinoite-testing.md) (for deeper context)

### Goal: A workflow run failed and I need recovery steps

1. [`docs/upstream-change-response.md`](./upstream-change-response.md)
2. [`docs/zfs-kinoite-testing.md`](./zfs-kinoite-testing.md) (for issue history/details)

### Goal: I need to update the akmods source pin

1. [`docs/akmods-fork-maintenance.md`](./akmods-fork-maintenance.md)
2. [`docs/upstream-change-response.md`](./upstream-change-response.md) (if validation fails)

## Where To Put New Documentation

1. Put term definitions in [`docs/glossary.md`](./glossary.md), not copied into every file.
2. Put newcomer overview content in [`README.md`](../README.md).
3. Put architecture/design reasoning in [`docs/architecture-overview.md`](./architecture-overview.md).
4. Put runbook/incident response steps in [`docs/upstream-change-response.md`](./upstream-change-response.md).
5. Put deep implementation history and hardening notes in [`docs/zfs-kinoite-testing.md`](./zfs-kinoite-testing.md).
6. Put workflow-command mapping details in [`.github/scripts/README.md`](../.github/scripts/README.md).
