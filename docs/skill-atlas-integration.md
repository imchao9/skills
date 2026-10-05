# Skill Atlas 集成边界

Skill Atlas 客户端独立于本仓库维护。本仓库只提供 Skills 内容、profile、来源锁定和组合清单；客户端负责扫描、分类、标签、Skill Set、桌面打包和调用统计。

## 文件系统契约

- 客户端通过 `SKILLS_ROOT` 指向本仓库的绝对路径；未设置时使用 `~/Documents/Me/skills`。
- Skill 以目录中的 `SKILL.md` 为发现入口，正式 profile 使用 `profiles/<profile>/.agents/skills/<skill-name>/SKILL.md`。
- `profiles/software-factory/software-factory-set.json` 和刷新脚本是可选集成。客户端找不到它们时，普通 Skill 扫描仍应可用。
- 客户端运行态数据使用 `SKILL_MANAGER_DATA_DIR`，默认是 `~/Library/Application Support/Skill Atlas`。标签、Skill Set 和 OTLP 事件不进入本仓库 Git。

## 本次拆分记录

- 客户端迁移基线：Skills 仓库提交 `5f5244a6`（已提交的真实目录/Electron/OTLP 版本）。
- 独立工作树：`/Users/cm/Documents/Me/skills-manager-client`。
- 原仓库中的 `admin/skill-manager-client` 已移除，避免客户端和 Skills 内容共用发布历史。
- 原 `.skill-manager/sets.json` 已迁移到 Skill Atlas 数据目录；原文件的备份位于本机 Codex backup 目录，不属于仓库内容。

客户端仍需由使用者单独初始化远程仓库、提交和推送；本次工作不执行外部 Git 写入。
