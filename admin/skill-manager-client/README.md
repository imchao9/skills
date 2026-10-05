# Skill Atlas

用于分类、打标签和管理本地 Skills 的客户端。默认扫描仓库根目录 `/Users/cm/Documents/Me/skills`，在 macOS 上与用户目录写法 `/Users/cm/Documents/me/Skills` 指向同一目录。

## 启动

```bash
cd /Users/cm/Documents/me/Skills/admin/skill-manager-client
npm install
npm run dev -- --host 0.0.0.0 --port 4173 --strictPort
```

打开 <http://localhost:4173/>。

## 打包成可双击客户端

在 Apple Silicon Mac 上执行：

```bash
cd /Users/cm/Documents/me/Skills/admin/skill-manager-client
npm run desktop:build
open "release/mac-arm64/Skill Atlas.app"
```

也可以直接运行 `npm run desktop` 预览桌面窗口。打包后的客户端自带本地页面和文件管理服务，启动后直接扫描 Skills 根目录，不需要先手动启动 Vite。

## 当前能力

- 扫描真实目录中的 `SKILL.md`，按 profile/category 展示。
- 搜索名称、路径、描述和标签，默认按一条条列表展示，也可切换网格视图。
- 支持跨分页多选、全选当前页、批量追加标签，并像购物车一样把已选 Skill 保存为 Set；Set 元数据写入 `.skill-manager/sets.json`，可继续加入或删除。
- 列表、卡片和详情支持快速打开 Skill 文件夹，直接在 Finder 中打开对应真实目录。
- 在详情面板预览 `SKILL.md`，标签保存到根目录 `.skill-manager/tags.json`。
- 新建 Skill 时真实创建分类目录和 `SKILL.md`。

## OTLP 调用统计

桌面客户端启动时会同时启动一个本机 OTLP/HTTP 接收端，默认监听 `127.0.0.1:4318`：

```text
POST http://127.0.0.1:4318/v1/traces
POST http://127.0.0.1:4318/v1/logs
POST http://127.0.0.1:4318/v1/metrics
```

接收端支持 OTLP JSON 和 `application/x-protobuf`。事件需要带有 Skill 维度，优先使用 `skill.name`，也兼容 `skill_name`、`skill.id`、`gen_ai.tool.name`、`tool.name`；没有属性时，形如 `skill.<name>` 的 span 名称也会识别。聚合数据保存在 Skills 根目录的 `.skill-manager/otlp-events.jsonl`，客户端会显示每个 Skill 的调用次数。

Codex 侧仍需要有 OTLP exporter 或 Hook 把 Skill 调用发到这个地址；仅启动接收端不会凭空产生调用事件。常见环境变量如下：

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_SERVICE_NAME=codex
```

如果 `4318` 已被占用，可以启动时设置 `OTLP_PORT`，并把 Codex exporter 指向对应端口。

可以通过 `SKILLS_ROOT=/absolute/path npm run dev` 指定其他 Skills 根目录。

## Software Factory 管理

如果 Skills 根目录包含 `profiles/software-factory/software-factory-set.json`，Skill Atlas 会显示 Software Factory 页面：

- 展示基础 skills、领域 packs、Matt 与 pstack 的锁定 commit；
- 对比组合 profile 与来源 profile 的 `SKILL.md` 内容，标记已同步、未同步和漂移；
- “检查来源”执行 `refresh_set.py --check`；
- “同步组合 profile”执行本地 `refresh_set.py`，只同步已声明的本地来源，不自动访问远程仓库；
- 普通 Skill Sets 仍保存在 `.skill-manager/sets.json`，与 software-factory manifest 分开管理。
