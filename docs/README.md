# VCO 文档索引

`docs/` 负责长期说明和最小治理导航。当前状态由 CI proof、GitHub Release 和本地 `check` 输出提供。

## Start Here

- [`install/README.md`](./install/README.md)：当前公开安装入口；说明默认 SkillsDir 路径、命令边界与补充文档

| 你要做什么 | 入口 |
| --- | --- |
| 安装或试用 | [`install/README.md`](./install/README.md) |
| 看懂安装边界和命令参考 | [`install/README.md`](./install/README.md) |
| 查看当前状态 | [CI proof](https://github.com/foryourhealth111-pixel/Vibe-Skills/actions/workflows/vco-gates.yml) / [最新 Release](https://github.com/foryourhealth111-pixel/Vibe-Skills/releases/latest) / `pwsh ./check.ps1` |
| 查看治理专题和 guardrails | [`governance/README.md`](./governance/README.md) |
| 查看设计说明和 playbook | [`design/README.md`](./design/README.md) |
| 查看外部工具和 overlay 边界 | [`external-tooling/README.md`](./external-tooling/README.md) |
| 理解变更规则 | [`developer-change-governance.md`](./developer-change-governance.md) |
| 理解系统结构 | [`architecture.md`](./architecture.md) |

## 按需再看

- [`cold-start-install-paths.md`](./cold-start-install-paths.md)：其他环境选择 SkillsDir 的简短说明

## Current Runtime

- 主技能合同：[`../SKILL.md`](../SKILL.md)
- 运行时协议：[`../protocols/runtime.md`](../protocols/runtime.md)
- 运行时真相合同：[`governance/current-runtime-field-contract.md`](./governance/current-runtime-field-contract.md)
- 路由兼容合同：[`governance/current-routing-contract.md`](./governance/current-routing-contract.md)
- 多代理协议：[`../protocols/team.md`](../protocols/team.md)
- bounded re-entry 与 host decision SOP：见 [`../SKILL.md`](../SKILL.md) 的 Structured host decision SOP；`vibe` 会在 `requirement_doc` 和 `xl_plan` 边界返回控制权，宿主需用 `--continue-from-run-id`、`--bounded-reentry-token`、`--host-decision-json` 继续
- 当前 CI 与 proof：[vco-gates](https://github.com/foryourhealth111-pixel/Vibe-Skills/actions/workflows/vco-gates.yml)
- 正式发布 proof：[最新 GitHub Release](https://github.com/foryourhealth111-pixel/Vibe-Skills/releases/latest)
- 本地运行时状态：在仓库根目录运行 `pwsh ./check.ps1` 或 `bash ./check.sh`

## Governance

- 文档结构规则：[`docs-information-architecture.md`](./docs-information-architecture.md)
- source-neutral 链接规则：[`governance/source-neutral-link-governance.md`](./governance/source-neutral-link-governance.md)
- 打包与兼容拓扑：[`version-packaging-governance.md`](./version-packaging-governance.md)
- 清洁度规则：[`repo-cleanliness-governance.md`](./repo-cleanliness-governance.md)
- 治理专题索引：[`governance/README.md`](./governance/README.md)
- 可观测性规则：[`governance/observability-consistency-governance.md`](./governance/observability-consistency-governance.md)
- 项目交付验收规则：[`governance/vibe-governed-project-delivery-acceptance-governance.md`](./governance/vibe-governed-project-delivery-acceptance-governance.md)

## Cross-Layer Handoff

- 机器可读配置：[`../config/index.md`](../config/index.md)
- 长期 reference：[`../references/index.md`](../references/index.md)
- 治理专题：[`governance/README.md`](./governance/README.md)
- 设计与 playbook：[`design/README.md`](./design/README.md)
- 外部工具边界：[`external-tooling/README.md`](./external-tooling/README.md)
- release 记录：[最新 GitHub Release](https://github.com/foryourhealth111-pixel/Vibe-Skills/releases/latest)

## Rules

- 根目录 `docs/*.md` 只放长期文档，不把 dated plans 或 batch reports 升格为长期合同。
- 安装说明以 [`install/README.md`](./install/README.md) 为主。
- specialized governance、design、external-tooling 叶子页优先放入对应 family 目录，避免继续堆回 `docs/*.md` 根层。
- 当前状态读取 CI artifact、GitHub Release proof 和本地 `check` 输出；仓库不维护手写状态快照。
- 更低层的脚本 operator surface 仍在 [`../scripts/README.md`](../scripts/README.md)；公开第一跳入口由本页提供。
- 新增长期入口时更新本页；dated 材料只更新对应子目录 `README.md`。
- 历史 dated 材料通过 git history 和 release artifact 恢复。
