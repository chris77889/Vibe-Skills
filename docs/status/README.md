# VCO Status

`docs/status/` 只放当前状态入口、proof contract、必要 guardrails，以及少量仍被 verify 直接消费的历史契约页。

## Start Here

- generated live summary: [vco-gates artifacts](https://github.com/foryourhealth111-pixel/Vibe-Skills/actions/workflows/vco-gates.yml)
- current closure receipt: [`closure-audit.md`](closure-audit.md)
- architecture sign-off proof: [`../proof/2026-04-04-owner-consumer-consistency-proof.md`](../proof/2026-04-04-owner-consumer-consistency-proof.md)
- batch order / next hop: [`roadmap.md`](roadmap.md)
- minimum proof contract: [`non-regression-proof-bundle.md`](non-regression-proof-bundle.md)
- protected surfaces: [`protected-capability-baseline.md`](protected-capability-baseline.md)
- transitional blockers: [`path-dependency-census.md`](path-dependency-census.md)

## Cross-Layer Handoff

- plans and historical batch context: [`../plans/README.md`](../plans/README.md)
- long-term promotion contracts: [`../universalization/platform-promotion-criteria.md`](../universalization/platform-promotion-criteria.md)

## Reading Boundary

- [vco-gates artifacts](https://github.com/foryourhealth111-pixel/Vibe-Skills/actions/workflows/vco-gates.yml)、[最新 GitHub Release](https://github.com/foryourhealth111-pixel/Vibe-Skills/releases/latest) 和本地 `check` 输出是当前优先阅读面。
- [`operator-dry-run.md`](operator-dry-run.md) 是 2026-03-12 的历史 dry-run 回执，只保留审计价值，不再承担当前批次回执角色。
- [`history-index.md`](./history-index.md) 是状态类历史索引入口，只在需要追历史批次或旧回执时再看。
- 其余仍留在本目录的 dated 页面，只有在 verify、proof bundle 或平台支持合同仍直接消费时才保留。
- 纯工作日志型状态页已从 GitHub 可见 docs 面清除。

## Rules

- CI 生成的 `current-state.json` 与 `current-state.md` 是 live summary；数值和 PASS/FAIL 回指同一 proof bundle。
- [`closure-audit.md`](closure-audit.md) 是当前批次回执；[`operator-dry-run.md`](operator-dry-run.md) 只是历史证据，不维护平行摘要。
- 结构性 sign-off 证明统一收束到 [`../proof/2026-04-04-owner-consumer-consistency-proof.md`](../proof/2026-04-04-owner-consumer-consistency-proof.md)。
- 更低层的 operator surface 仍在 [`../../scripts/README.md`](../../scripts/README.md)，但它不是当前状态阅读的第一跳入口。
- verify 的精确 run order 仍以 [`../../scripts/verify/gate-family-index.md`](../../scripts/verify/gate-family-index.md) 为准，但它不是当前状态阅读的第一跳入口。
- dated baselines 只保留 guardrail、proof bundle 或 verify 消费作用；零消费者历史正文不再留在 `docs/status/`。
