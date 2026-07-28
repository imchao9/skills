# TAPD CLI 操作示例

把以下命令作为起点，执行前通过现场 `--help` 确认当前参数。

## 发现工作区和条目

```bash
tapd --help
tapd workspace list
tapd workspace info --workspace-id <workspace-id>
tapd url '<tapd-url>'
```

详情 URL 优先使用 `tapd url`。列表或视图 URL 必须保留完整 URL 和全部查询参数；
CLI 可能解析出工作区，但不能假定它能够复现 `conf_id` 保存视图。单次任务优先使用
`--workspace-id`，不要持久化切换工作区。

注入或测试令牌前先读取[认证说明](authentication.md)。

## 用浏览器兜底读取列表 URL

只有 CLI/MCP 认证不可用，且已授权的登录浏览器可以打开准确 TAPD URL 时才使用此方式。

1. 从路径解析工作区和条目类型。
2. 保留全部查询参数，尤其是 `categoryId`、`sort_name`、`order`、`conf_id` 和 `useScene`。
3. 打开或接管准确页面，不要改变筛选条件或视图。
4. 读取视图名、可见筛选范围、总数、表头、排序标记和表格行。
5. 比较总数和已渲染行数。存在更多数据时使用可见分页控件，不要编造 `queryToken`。
6. 返回可用的短 ID、长 ID、筛选条件和分页覆盖。

提取数据时不要点击创建、编辑、保存、清空筛选、保存视图、导出、选择或其他改变状态的控件。

## 读取工作项

```bash
tapd story show <story-id> --workspace-id <workspace-id>
tapd task show <task-id> --workspace-id <workspace-id>
tapd bug show <bug-id> --workspace-id <workspace-id>
```

详情默认输出精简 Markdown。只有需要提取准确字段时才增加 `--json`。

## 列表与筛选

```bash
tapd story list --workspace-id <workspace-id> --filter 'name=LIKE<登录>'
tapd bug list --workspace-id <workspace-id> --filter 'created=>2026-01-01'
tapd task list --workspace-id <workspace-id> --filter 'owner=USER_OR<张三|李四>'
tapd story list --workspace-id <workspace-id> \
  --filter 'status=CONTAINS_OR<开发中|测试中>'
```

多个 `--filter` 条件组合使用。高级操作符包括 `LIKE`、`EQ`、`NOT_EQ`、
`LIKE_OR`、`CONTAINS`、`CONTAINS_OR`、`USER_OR`、比较、范围和多值 OR。
使用自定义字段前先核对字段名：

```bash
tapd custom-field list --entity-type stories --workspace-id <workspace-id>
```

过滤需求、任务、缺陷或迭代列表时，除非已检查安装版本，否则不要相信响应中的 `total`
或 `has_more`。已审计版本通过另一条忽略大多数列表筛选条件的 count 请求生成这两个字段。
分页时使用实际 `items` 数量：当前页条数等于 `limit` 时才请求下一页，最后自行合计返回条数。

## 状态汇报

分别执行数量和迭代命令，使单项失败保持可见：

```bash
tapd story count --workspace-id <workspace-id>
tapd bug count --workspace-id <workspace-id>
tapd task count --workspace-id <workspace-id>
tapd iteration list --workspace-id <workspace-id>
```

应用用户要求的状态、日期和处理人筛选，完成必要分页，并汇报：

- 工作区 ID 和名称；
- 生成时间和时区；
- 需求、缺陷和任务数量；
- 相关迭代 ID、名称、状态和日期范围；
- 筛选条件、分页覆盖和不可用部分。

## 准备流程变更

更新状态或流程相关字段前执行：

```bash
tapd workitem-type list --workspace-id <workspace-id>
tapd workflow status-map --system story \
  --workitem-type-id <workitem-type-id> --workspace-id <workspace-id>
tapd workflow transitions --system story \
  --workitem-type-id <workitem-type-id> --workspace-id <workspace-id>
tapd workflow last-steps --system story \
  --workitem-type-id <workitem-type-id> --workspace-id <workspace-id>
tapd story show <story-id> --workspace-id <workspace-id> --json
```

写入前立即读取目标命令帮助：

```bash
tapd story update --help
tapd bug update --help
tapd iteration update --help
```

只使用现场帮助确认的参数。写入成功后执行对应 `show` 命令，重新验证变更字段。

## 评论、工时、关联和消息

以下命令即使不更新主工作项，也会改变外部状态：

```bash
tapd comment add --help
tapd timesheet add --help
tapd relation create --help
tapd qiwei send --help
```

必须获得用户明确授权，确认准确目标，只执行一次，并通过读取或结构化成功响应完成验证。
