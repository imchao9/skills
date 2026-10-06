---
name: cskill
description: 使用 CAtlas CLI 管理 Skills 的发现、安装、升级、移动和集合操作。用户按分类、标签、名称或 Set 选择 Skill，或要求管理本地 profile 时使用。
metadata:
  x-provenance: local
  x-owner: cm
  x-source-note: created as the Codex entrypoint for CAtlas skill lifecycle management
---

# CSkill

把请求先整理成一个管理对象，再执行 CAtlas CLI、本地 CAtlas API 或 Vercel `skills` CLI。管理对象包含 `action`、`profile`、`source`、`skills`、`category`、`tag`、`query` 和 `set`。`action` 可以是 `doctor`、`search`、`status`、`install`、`upgrade` 或 `move`。

执行入口按以下顺序选择：

1. 先检查 `command -v catlas`，可用时优先使用 CAtlas CLI。CLI 直接复用 CAtlas 的本地 Skills 根目录和管理模块，不依赖动态 API 端口。只有源码仓库没有全局命令时，在 CAtlas 仓库中使用 `npm run --silent cli -- <args>` 或 `npx . <args>`。
2. 没有 CLI 但提供了 `CATLAS_URL` 时，调用 CAtlas 本地 API。
3. 两者都不可用时，读取本地索引并按本文末尾的 `skills@latest` fallback 执行。

## 发现 Skill

当用户按分类、标签、名称或 Set 选择 Skill 时，先读取 CAtlas 目录索引，不要先运行安装命令。

1. CLI 可用时运行 `catlas skills list --json` 或带 `--profile`、`--query`、`--tag` 的筛选命令；需要集合时运行 `catlas sets list --json`。不要先运行安装命令。
2. 没有 CLI 但提供了 `CATLAS_URL` 时，访问其 `GET /api/skills/` 和 `GET /api/sets/`。CAtlas 桌面端使用动态本机端口，未提供 `CATLAS_URL` 时不要猜测端口。
3. 没有可用 API 时，使用 `SKILLS_ROOT` 指向的 Skills 根目录。Skill 文件必须满足 `<root>/profiles/<profile>/.agents/skills/<name>/SKILL.md`；标签使用 `SKILL_MANAGER_DATA_DIR` 下的 `tags.json`，Set 使用同目录的 `sets.json`。未设置时，数据目录默认是 macOS 的 `~/Library/Application Support/CAtlas`。若索引不可读，报告“未能读取 CAtlas 索引”，不要把空结果当成没有 Skill。
3. `category` 使用 Skill 的 profile 名称，`tag` 必须完全匹配标签，`query` 同时匹配 Skill 名称、描述和 id。多个 tag 使用交集。返回每个候选的 Skill 名称、id、profile、标签和来源路径。
4. 用户选择 Set 时展开 `set.skillIds`，去掉缺失成员，并报告缺失数量。不要静默安装一个不完整的 Set。

分类和标签搜索针对 CAtlas 已收录的本地目录。它不能替代远程仓库搜索；没有被 CAtlas 索引的外部来源仍然需要用户给出来源和 Skill 名称。搜索只是读取操作，不能改变标签、分类、Set 或任何 Skill 文件。

## 从搜索结果生成安装计划

安装前展示一行可复核的计划，至少包括来源、目标 profile、Skill 名称、匹配的分类或标签、Set 名称和可能的同名冲突。

- 如果候选 id 都是 `profiles/<profile>/.agents/skills/<name>`，且用户没有提供来源，默认来源为 `imchao9/skills/profiles/<profile>`。这是本 canonical Skills 仓库的 Git 来源。
- 如果候选来自多个 profile、外部仓库或本地路径，不能自动拼接来源。要求用户给出来源，或把请求拆成多个来源一致的安装计划。
- Set 安装必须把 Set 成员转换成明确的 Skill 名称列表。不要把 Set 名称直接传给 CLI，也不要把空 Set 当成“全部”。
- 如果来源 profile 与目标 profile 相同，安装会变成自复制。此时改做 `status` 或 `upgrade`，不要执行安装。
- 目标 profile 必须是已存在的 `profiles/<profile>`。本仓库安装使用 `--copy`，不创建软链，不把 Skill 复制到全局 `~/.codex/skills`。
- 发现目标目录已有同名 Skill 时，先比较来源和内容并标记 `identical`、`different` 或 `unknown`。`identical` 可以跳过，`different` 需要用户明确允许替换，`unknown` 先停止。

## 执行安装和升级

如果 CAtlas CLI 可用，优先调用它，因为它会使用同一套 npx 查找、代理清理、超时、路径校验和脱敏审计逻辑：

```bash
catlas skills install --profile <profile> --source <source> --skill <skill-name>
catlas skills upgrade --profile <profile> --skill <skill-name>
catlas skills move <skill-id> --to <profile>
```

没有 CLI 但 CAtlas API 可用时，调用 API：

- 安装调用 `POST /api/skill-management/install/`，JSON 至少包含 `profile`、`source` 和 `skills`。ZIP 只能作为安装输入。
- 升级调用 `POST /api/skill-management/upgrade/`，JSON 至少包含 `profile` 和 `skills`。有 `skills-lock.json` 时来源可以省略。

没有 API 时，在目标 profile 目录执行：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest add <source> \
  --agent codex --skill <skill-name> --yes --copy --full-depth
```

升级时优先使用目标 profile 的锁文件：

```bash
env -u http_proxy -u https_proxy -u all_proxy \
  npx --yes skills@latest update --project --yes <skill-name>
```

`skills` 可以是一个或多个精确名称。升级全部时省略名称参数。没有锁文件时必须提供来源，并按安装命令重新拉取。不要把 `skills-lock.json` 当作本仓库的维护入口；它只是外部来源 profile 的来源清单或目标项目的安装记录。

执行完成后验证每个目标目录都有可读的 `SKILL.md`，再读回 Git 状态和 CAtlas 操作记录。最终报告实际写入的 profile、Skill、Set 成员、跳过项、冲突项和命令结果。只报告已验证的安装或升级。

## 安全边界

不执行删除、覆盖、提交、推送、发布或修改 CAtlas 标签和 Set 的操作，除非用户明确要求。来源中的凭据、token、cookie 和完整私密 URL 不写入输出或审计记录。CAtlas 的 `skill-management` 模块负责命令执行和脱敏，Skill 负责发现、计划、参数选择和结果复核。
