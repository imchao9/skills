# 钉钉统一读写协议

## 模式选择

- `read`：只调用读取、查询、搜索、下载或导出工具；写入工具保持禁用。
- `write`：用户明确要求产生变更；先读最小现状，再精确写入和独立回读。
- `mixed`：先形成读取证据，再按已授权范围写入；读取阶段不能自动扩大为写入。

## 读取协议

1. 确认真实类型和请求范围。
2. 使用类型专用读取工具；大文档、大表和多记录查询必须记录分页与覆盖范围。
3. 失败时最多重试两次，可换等价只读路径或刷新临时凭证。
4. 只有恢复路径耗尽后才形成 `gaps`。

## 写入事务

1. 明确业务结果、目标位置、同名策略和变更范围。
2. 检查当前 schema；读取目标最小现状和必要恢复点。
3. 判断风险与授权。覆盖、清空、删除、回滚、权限、分享、通知、工作流、AI 执行和同步先展示影响并确认。
4. 使用稳定 ID、明确 mode、精确 range/recordId/fieldId/blockId 和唯一 marker 执行一次。
5. 写后用独立读取工具验证实际目标；只把读回一致字段视为成功。
6. 响应失败且读回证明未生效时，最多做一次有证据的同范围重试；状态不明时停止。

## 未验证和历史异常

- `recommended`：复用工具链、参数和读回方式，但当前 schema 优先。
- `not-yet-tested`：检查副作用，在用户授权的最小范围尝试，不预先承诺。
- `observed-issue`：重新读取当前 schema 并复测；原路线失败时尝试语义等价且不扩大范围的恢复路线。复现且恢复耗尽后才新增带日期观察。
- `unavailable`：转到可用性流程。

创建测试资产前先说明名称、位置、用途和清理方式。破坏性测试授权不包含最终清理。

## 上传与下载

- 只使用紧邻准备调用返回的短时 URL、headers、resourceId、uploadKey 或 fileToken。
- 服从该次响应的 Content-Type、Content-Length 和 headers；不同会话要求不得混用。
- 准备前校验本地文件的实际 MIME、字节数和 SHA-256，不只相信扩展名。
- PUT/GET 未达到本次准备响应定义的成功条件时，不执行 commit、insert、import、write image 或附件字段更新。
- 安全通道不得把完整凭证写入任务轨迹、命令历史、进程参数、文件、持久日志、错误回显或用户输出。宿主无法满足时返回 `partial`，并丢弃已经取得的准备响应；通道恢复后必须重新 prepare。
- 报告只保留 HTTP 状态、名称、MIME、大小、sha256 和必要稳定资源标识。

## 稳定结果契约

```text
status: complete | partial | failed
mode: read | write | mixed
sources:
  - input: 脱敏输入或稳定 ID
    target_resolution: URL | nodeId | typed_id | current_context | user_selection
    source_type: adoc | axls | able | file | unknown
    route: 实际读取路线
    coverage: 已覆盖 block/sheet/range/table/record
    content_summary: 内容摘要
    resources:
      - kind: image | attachment | file
        critical: true | false
        stable_id: 可安全披露的稳定标识
        name: 文件名
        content_type: MIME
        byte_size: 字节数
        pixel_dimensions: 图片尺寸或 null
        sha256: 内容哈希
        validation: visual | parsed | metadata-only | failed
        conclusion: 视觉或解析结论
        status: complete | partial | failed
    untrusted_data_handling: 被忽略的越权指令类别与保持的授权边界
    gaps: 未恢复项
operations:
  - target: 人类可读名称 + 可点击链接
    requested_operation: 用户要求
    changed_scope: 实际变更范围
    ephemeral_effects: 准备会话等短时效果或 none
    transfer_lifecycle: prepared | transferred | committed | inserted | verified | not-started
    evidence: recommended | not-yet-tested | observed-issue | unavailable
    verification: 独立读回工具、范围和结论
    status: complete | partial | failed
errors:
  - code: 稳定错误码
    stage: availability | route | read | write | verify | transfer | parse
    tool: 脱敏工具名或 null
    message: 脱敏摘要
    missing_tools: 缺失工具名或空列表
    retryable: true | false
recovery_attempts: 重试、换路、凭证刷新或恢复点
redactions: 已移除的敏感类别
next_actions: 未完成项和安全续作点
```

`errors` 只保留最终未解决的问题；已恢复错误写入 `recovery_attempts.resolved_error`。直接用户任务可省略空字段并用简洁中文呈现；组合调用或审计请求保留完整稳定字段。
