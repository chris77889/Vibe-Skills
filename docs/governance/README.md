# Governance

- Up: [`../README.md`](../README.md)

## Conclusion

Start here only for the current governance contracts that still describe the live runtime boundary.

If you are reading old consolidation, cleanup, or hard-removal passes, go to [`../archive/governance-history/README.md`](../archive/governance-history/README.md) instead.

## Current Entry Surfaces

current runtime truth and routing compatibility contracts live here first.

- [`../../config/live-document-contract.json`](../../config/live-document-contract.json)
  is the executable inventory for the bounded live-document surface and the
  shared requirement, plan, status, and proof artifact sink. Manifest artifact
  paths resolve relative to the declared per-run artifact root.
- [`current-runtime-field-contract.md`](current-runtime-field-contract.md)
  defines the current runtime truth vocabulary and the work-first artifact order.
- [`current-routing-contract.md`](current-routing-contract.md)
  explains the remaining routing compatibility mirrors after you already checked the runtime truth contract.
- [`skill-admission-hardening.md`](skill-admission-hardening.md)
  records the current admission rules for what may enter the governed skill surface.
- [`bundled-skill-retention-matrix.md`](bundled-skill-retention-matrix.md)
  explains the current starter-set boundary and why the large repo-owned bundled tree is not the default public extension story.
- [`kernel-first-remediation-baseline.md`](kernel-first-remediation-baseline.md)
  freezes the current remediation boundary while the kernel-first cleanup is still in progress.

## What Does Not Start Here

These are not current entry surfaces:

- [`historical-routing-terminology.md`](historical-routing-terminology.md)
  is only for reading older routing cleanup records. It is not the current routing model.
- dated consolidation batches
- dated cleanup passes
- dated hard-removal records
- zero-route-authority migration passes

Those materials can still be useful, but they are history. They should be reached through the archive navigation, not treated as the first explanation of the current runtime.
