# Software factory set

这是一个可复用的组合 profile，不是新的大而全 skill 集合。它把一个 `software-factory` 路由器和 11 个 Matt 工程 skill 组合成最小的软件构建流水线；pstack 的编排、并行和验证方法保存在路由器的 Codex 适配文档中。

`software-factory-set.json` 是组合成员的 manifest：它记录每个 Skill 的来源 profile、来源路径、职责和可选 pack。`.agents/skills/` 是生成目录，不是组合关系的唯一事实来源。

## 包含内容

| 类别 | Skills |
|---|---|
| 入口 | `software-factory` |
| 需求与架构 | `grill-with-docs`, `domain-modeling`, `codebase-design` |
| 计划 | `to-spec`, `to-tickets` |
| 实现 | `implement`, `implement-spec`, `tdd` |
| 质量 | `diagnosing-bugs`, `code-review` |
| 交付 | `pr` |

安装一次后，由 `software-factory` 根据阶段使用其中一部分；不会在每次对话里加载全部内容。

## 领域 packs

基础 set 不绑定具体技术栈。按项目选择 pack：

| Pack | 内容 | 适用场景 |
|---|---|---|
| `frontend` | `frontend-delivery-workflow`, `draw-ui`, `huashu-design`, `vitest-midscene-e2e` | 前端、UI、浏览器验收 |
| `backend-java` | `java-backend-code-review`, `java-backend-knowledge-base` | Java 后端 |
| `backend-codemao` | `codemao-troubleshoot`, `crp-deploy` | Codemao 服务诊断和 CRP 交付 |
| `testing` | `ai-intelligent-test`, `vitest-midscene-e2e` | 测试设计和 E2E |
| `research` | `agent-reach`, `grok-research` | 外部资料和证据检索 |

激活时使用 `--pack frontend` 或 `--pack backend-java`。Pack 只是按需安装的能力集合，不会自动进入全局运行态。

## 更新

1. 更新 `profiles/mattpocock-skills`，确认新的 upstream commit 和 lock。
2. 更新 `software-factory-set.json` 中的 Matt commit。
3. 先校验 manifest 和来源 Skill：

   ```bash
   python3 scripts/refresh_set.py \
     --repo /Users/cm/Documents/Me/skills \
     --check
   ```

4. 本机共研时，可以让组合 profile 的每个 Skill 软链到来源 profile。软链只适合同一台机器的本地开发，不要把这种结果作为跨机器发布物：

   ```bash
   python3 scripts/refresh_set.py \
     --repo /Users/cm/Documents/Me/skills \
     --mode symlink
   ```

5. 提交或通过 Git source 发布前，生成实体文件：

   ```bash
   python3 scripts/refresh_set.py \
     --repo /Users/cm/Documents/Me/skills \
     --mode copy
   ```

   `copy` 是默认模式。它把 manifest 解析出的每个 Skill 复制到组合 profile，保持 `npx skills` 和 Git source 能直接读取 `SKILL.md`。
6. 检查生成的 `skills-lock.json` 和 Git 变更，再提交。

## npx skills 安装和 lock

目标项目从已经推送的 Git source 安装组合 profile：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/software-factory \
  --agent codex --skill '*' --yes --copy --full-depth
```

只安装基础 set 中的一个 Skill：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add imchao9/skills/profiles/software-factory \
  --agent codex --skill software-factory --yes --copy --full-depth
```

`npx skills` 会在目标项目生成 profile 级 `skills-lock.json`，记录 source、ref、skillPath 和 hash。这个 lock 是安装来源和完整性记录，不是当前仓库 manifest 的替代品；组合成员关系仍由 `software-factory-set.json` 管理。跨机器安装应使用已推送的 Git source 和稳定 ref，不要把本地 `working-tree` lock 当成发布入口。

pstack 不作为可直接安装的 Cursor plugin；它的来源 commit 记录在 manifest 和 `UPSTREAM.md`，更新时重新审阅其 `poteto-mode`、`feature`、`orchestrate` 和 verification 方法，再修改 `software-factory` 适配层。
