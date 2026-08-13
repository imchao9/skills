# AI Code Review 报告

## 报告信息

| 字段 | 内容 |
| --- | --- |
| 审查快照ID | 16ae6e26-ae55-4240-bf13-1ad7ff74614f |
| 团队 | platform-informatization |
| 项目 | platform-informatization-manage-system |
| 目标类型 | mr |
| MR | https://gitlab.codemao.cn/backend/platform-informatization/internal-service/platform-informatization-manage-system/-/merge_requests/307 |
| 分支 | feature/link -> master |
| 版本 | 13c14eaa0923524ac844ca25406e7517c3acd4cd..72ab8c40f16f2460f054e63607c70d82d445dfe2 |
| 生成时间 | 2026-08-13T07:38:26.324100+00:00 |

## 风险摘要

- Issue 总数: 4
- P0: 1
- P1: 2
- P2: 1
- P3: 0

## 重点问题汇总表

| Issue | 优先级 | 问题描述 | 问题分类 | 审查状态 | 文件 | 详情跳转 |
| --- | --- | --- | --- | --- | --- | --- |
| Issue-1 | P0 | 链接巡检把整批目标一次性提交到无界线程池队列 | performance | open | platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/impl/ProtocolLinkAlarmServiceImpl.java:102 | [Issue-1](#issue-1) |
| Issue-2 | P1 | 全量扫描没有整轮截止时间或工作量预算 | performance | open | platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/impl/ProtocolLinkAlarmServiceImpl.java:139 | [Issue-2](#issue-2) |
| Issue-3 | P1 | HTML 大小与并发可独立调到危险组合，解析过程会复制多份全文 | performance | open | platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/protocolcontent/ProtocolContentInspector.java:47 | [Issue-3](#issue-3) |
| Issue-4 | P2 | JDK HTML 3.2 解析器无法按当前回调逻辑忽略 HTML5 template 内容 | correctness | open | platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/protocolcontent/ProtocolContentInspector.java:333 | [Issue-4](#issue-4) |

## Issue 详情

<a id="issue-1"></a>

### Issue-1 P0 链接巡检把整批目标一次性提交到无界线程池队列

- finding_key: `a95d33ad166a5c2e`
- rule_id: `PERF-QUEUE-001`
- category: `performance`
- location: `platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/impl/ProtocolLinkAlarmServiceImpl.java:102`
- status: `open`

**证据**

Executors.newFixedThreadPool 使用无界 LinkedBlockingQueue；checkTargets 在消费任何完成结果前，先把 batchTargets 中全部唯一链接 submit，并额外用 futures 保存所有 Future。batchTargets 没有链接数量上限，而 protocolBatchSize 最大允许 1000、单页最大允许 10 MiB；同时 linkStates 还会保留整轮全部唯一 URL 及来源。

**影响**

单个异常或超大批次即可在固定工作线程之外堆积大量 Runnable、Future、LinkState 和来源映射，触发长时间 Full GC 或 OOM。该任务与业务接口共享同一 JVM，内存压力会直接影响整个服务，而不只是让 Job 自身变慢。

**建议**

改为显式 ThreadPoolExecutor 和有界队列，并采用最多维持 checkConcurrency 个在途任务的滑动提交/消费方式；为每页链接数、每批唯一链接数及整轮唯一链接数设置硬上限。不要为了避免拒绝而使用无界队列；到达容量时应停止本轮并上报容量失败。

<a id="issue-2"></a>

### Issue-2 P1 全量扫描没有整轮截止时间或工作量预算

- finding_key: `761c3b93c451f8b3`
- rule_id: `PERF-DEADLINE-001`
- category: `performance`
- location: `platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/impl/ProtocolLinkAlarmServiceImpl.java:139`
- status: `open`

**证据**

scanProtocols 会一直 keyset 分页到所有已发布协议结束；协议页面在 for 循环中串行 fetch。默认单请求连接/读取超时为 2s/5s，链接检查还允许一次重试和最多 5 次重定向，但整轮没有 deadline、最大协议数、最大 HTTP 请求数或取消令牌。另一个内容巡检 Job 也会独立全量下载相同协议页面，代码内没有跨任务或跨轮 single-flight 保护。

**影响**

运行时间随协议数和唯一链接数线性增长；慢站点下链接任务可能运行数十分钟甚至更久，并持续占用专用线程、连接、CPU、堆和出口带宽。若调度频率/阻塞策略配置不当，或两个巡检任务时间重叠，资源占用会叠加并影响业务请求。

**建议**

增加可配置且有安全上限的整轮 deadline、最大协议数/链接数/请求数，并在分页、页面下载和链接检查之间检查取消状态；在应用侧增加 single-flight/分布式互斥，至少确保同一 Job 不重叠。上线验收必须用生产协议量测得 P95/P99 单轮耗时，再据此设置 XXL-JOB 串行阻塞策略和调度间隔，并错开两个全量巡检。

<a id="issue-3"></a>

### Issue-3 P1 HTML 大小与并发可独立调到危险组合，解析过程会复制多份全文

- finding_key: `d9bb8b1cedae8412`
- rule_id: `PERF-HEAP-001`
- category: `performance`
- location: `platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/protocolcontent/ProtocolContentInspector.java:47`
- status: `open`

**证据**

每页先被完整读入 byte[] 再构造成 String；解析回调又同时累积 visibleText 和 plainText，随后 visibleText.toString()、normalizeWhitespace 的 StringBuilder/String 再产生全文级副本。配置允许 scanConcurrency=50 与 maxProtocolBodyBytes=10 MiB 同时生效，validateRuntime 只分别校验上下限，没有总内存预算。默认值也允许 10 个 2 MiB 页面并发解析。

**影响**

解析算法虽然是单次事件扫描，但端到端并非流式，峰值堆占用约为并发数乘以每页多份字节/字符缓冲；极端合法配置可轻易达到数 GiB，默认配置在大页面下也可能产生明显 GC 抖动，拖慢整个 JVM。

**建议**

把 maxProtocolBodyBytes 与 scanConcurrency 联合校验为固定总预算，并显著收紧最大值；优先直接从受限 Reader 流式解析，避免 byte[] -> String 及多份全文 StringBuilder。若业务仍需两条文本流，至少只保留规则实际需要的有限上下文/URL，增加大页面并发压力测试和堆峰值验收。

<a id="issue-4"></a>

### Issue-4 P2 JDK HTML 3.2 解析器无法按当前回调逻辑忽略 HTML5 template 内容

- finding_key: `86d7e10334fd4d78`
- rule_id: `HTML-PARSER-001`
- category: `correctness`
- location: `platform-informatization-manage-system-service/platform-informatization-manage-system-admin-service/src/main/java/cn/codemao/service/platform/informatization/manage/system/service/protocolcontent/ProtocolContentInspector.java:333`
- status: `open`

**证据**

ParserDelegator 固定加载 html32 DTD。对 `<template>hidden https://x.test</template>` 的现场回调结果是两个 handleSimpleTag(template)，中间仍触发 handleText；当前 ignoredDepth 只在 handleStartTag/handleEndTag 中处理 template，handleSimpleTag 只处理边界，因此隐藏模板文本会进入 visibleText/plainText。

**影响**

协议包含 HTML5 template 时，模板中的历史地址、隐私政策字样或明文 URL 会被当作可见正文，产生错误告警。相同的 HTML5/unknown-tag 语义差异也构成后续规则扩展风险。

**建议**

优先使用明确支持 HTML5 解析语义的服务端解析器；若必须保持零依赖，应识别 HTML.UnknownTag 及结束标记属性来维护 template 深度，并补充 template、现代语义标签、畸形 HTML 的回归测试。链接 `<a>` 提取可保留当前事件式思路。

## 剩余盲点

- 数据库 MCP 离线，无法确认 pt_template_protocol 的 publish_status,id 联合索引及生产基数。
- 生产 XXL-JOB 调度表达式、路由策略、阻塞策略和两个巡检任务是否错峰不在仓库内，无法现场确认。
- 定向 Maven 测试受本机 Java 21 与旧 Lombok 的模块访问错误阻断，未得到测试执行结果；失败发生在未触及的 API 模块编译阶段。
- 未使用生产协议样本做耗时、峰值堆、GC 和出口带宽压测。
