# CM Tool Marketplace

## 定位

`cm-tool-marketplace` 是公司内部 Codex Plugin Marketplace，不是普通 Skill
source，也不是 `profiles/codemao` 的上游来源。

- Canonical source：
  `git@gitlab.codemao.cn:backend/platform-informatization/tool/cm-tool-marketplace.git`
- Marketplace name：`codex-usage-local`
- 最近审查：2026-07-24
- 审查 commit：`d1b6dcb1615e9ddf77124292b29785755f155522`
- License：`UNLICENSED`，仅按公司内部资产管理

插件必须通过 Codex Plugin Manager 安装和升级。不得把插件提供的 skill
复制到 `profiles/codemao/.agents/skills/`、`profiles/global-runtime`，也不得把
该仓库写进 `profiles/codemao/skills-lock.json`。

## 当前纳管插件

| Plugin | 审查版本 | 当前状态 | 用途 |
|---|---:|---|---|
| `codex-usage` | `0.1.33` | 已安装、已启用 | Codex usage 采集、查询和运行状态检查 |
| `codemao-fullstack-workflow` | `0.1.21` | 已安装、已启用 | 公司全栈交付工作流、诊断命令和配套 skill bundle |

上述版本来自 2026-07-24 对 marketplace source 和本机
`codex plugin list` 的交叉核验。

## 安装与升级

首次配置 marketplace：

```bash
codex plugin marketplace add \
  git@gitlab.codemao.cn:backend/platform-informatization/tool/cm-tool-marketplace.git
```

按需安装插件：

```bash
codex plugin add codex-usage@codex-usage-local
codex plugin add codemao-fullstack-workflow@codex-usage-local
```

刷新该公司内源 marketplace：

```bash
codex plugin marketplace upgrade codex-usage-local
```

升级 marketplace snapshot 不等于自动安装所有插件。执行安装或升级前，先用
`codex plugin list` 确认当前状态；操作完成后重启 Codex，让新版本能力进入新会话。

## 验证

```bash
codex plugin marketplace list
codex plugin list
```

验收要求：

1. `codex-usage-local` marketplace 可见，来源指向 canonical GitLab 仓库。
2. 两个已纳管插件均显示为 installed、enabled，版本与预期一致。
3. 重启 Codex 后，新会话可以发现对应的 skill、命令或 MCP 工具。
4. `codemao-fullstack-workflow` 可按其插件说明运行 doctor；失败时保留错误证据，
   不通过复制内部 skill 绕过插件依赖。

## 治理与安全边界

- 本文只记录公司内源 plugin 的来源、安装态、升级和验证方法；全量安装态见
  [`../codex-plugins-inventory.md`](../codex-plugins-inventory.md)。
- 插件内的 `source-command-*` skill 依赖同一插件提供的脚本和命令，
  `codex-usage` 依赖插件 MCP；拆成独立 skill 会破坏运行契约。
- `codemao-fullstack-workflow` 包含 best-effort 低敏遥测。升级时需复核 manifest
  中的 endpoint、采集字段和失败策略，不得上传 prompt、代码、diff、原始会话、
  凭证或完整本机路径。
- Marketplace 升级属于外部更新操作，不纳入每日 skills 自动更新，也不自动
  晋级任何新插件。新增插件必须有明确真实场景并经过人工审查。
- 不自动 push、发布或修改 marketplace 仓库；本仓库只维护治理记录。
