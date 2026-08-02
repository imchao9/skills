# Output Contract

Use this concise Chinese structure:

```text
【AI Test 运行诊断】
范围：<run id / report dir / case id>
Runner 状态：<executionStatus + counts>
证据完整性：<evidenceStatus + missing/unparsed facts>
目标状态：<reached / not-reached / unknown + observed evidence>
业务结论：<verified-pass / verified-fail / unverified>
总体判定：<VERIFIED_PASS / VERIFIED_FAIL / INVALID_RUN / INCONCLUSIVE>
失败归类：<category>（置信度：high|medium|low）
关键证据：
- <artifact and observation>
未知项：
- <what the artifacts cannot prove>
下一步：<smallest action that closes the uncertainty>
```

For a batch, list per-case exceptions before giving the batch verdict. One invalid or inconclusive case prevents a batch-level `VERIFIED_PASS`.
