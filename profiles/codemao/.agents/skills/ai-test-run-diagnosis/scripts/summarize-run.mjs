#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const VALID_STATUSES = new Set(['passed', 'failed', 'error', 'skipped']);

function fail(message) {
  process.stderr.write(`ai-test-run-diagnosis: ${message}\n`);
  process.exitCode = 1;
}

function parseArgs(argv) {
  const result = { json: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--json') result.json = true;
    else if (arg === '--help' || arg === '-h') result.help = true;
    else if (['--report', '--since', '--case'].includes(arg)) {
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) throw new Error(`${arg} requires a value`);
      result[arg.slice(2)] = value;
      index += 1;
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }
  if (!result.help && Boolean(result.report) === Boolean(result.since)) {
    throw new Error('provide exactly one of --report or --since');
  }
  return result;
}

function helpText() {
  return [
    'Usage:',
    '  node summarize-run.mjs --report <run-dir|manifest.json> [--case <id>] [--json]',
    '  node summarize-run.mjs --since <ISO timestamp> [--case <id>] [--json]',
    '',
    '--since searches midscene_run/report and succeeds only when exactly one run matches.',
  ].join('\n');
}

function readJson(filePath, label) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (error) {
    throw new Error(`cannot read ${label} ${filePath}: ${error.message}`);
  }
}

function resolveExplicitReport(input) {
  const resolved = path.resolve(input);
  const manifestPath =
    path.basename(resolved) === 'manifest.json' ? resolved : path.join(resolved, 'manifest.json');
  if (!fs.existsSync(manifestPath)) throw new Error(`manifest not found: ${manifestPath}`);
  return { reportDir: path.dirname(manifestPath), manifestPath };
}

function resolveSinceReport(input) {
  const since = new Date(input);
  if (Number.isNaN(since.getTime())) throw new Error(`invalid ISO timestamp: ${input}`);
  const root = path.resolve('midscene_run/report');
  if (!fs.existsSync(root)) throw new Error(`report root not found: ${root}`);

  const matches = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const reportDir = path.join(root, entry.name);
    const manifestPath = path.join(reportDir, 'manifest.json');
    if (!fs.existsSync(manifestPath)) continue;
    const manifest = readJson(manifestPath, 'manifest');
    const generatedAt = new Date(manifest.generatedAt);
    if (!Number.isNaN(generatedAt.getTime()) && generatedAt >= since) {
      matches.push({ reportDir, manifestPath, generatedAt: generatedAt.toISOString() });
    }
  }
  if (matches.length !== 1) {
    const names = matches.map((item) => path.basename(item.reportDir)).join(', ') || 'none';
    throw new Error(`--since must resolve exactly one report; found ${matches.length}: ${names}`);
  }
  return matches[0];
}

function resolveArtifact(reportDir, artifactPath) {
  return path.isAbsolute(artifactPath) ? artifactPath : path.join(reportDir, artifactPath);
}

function unique(values) {
  return [...new Set(values)];
}

function summarizeCase(reportDir, item, auditCase) {
  if (!item || typeof item !== 'object') throw new Error('manifest contains an invalid case');
  if (!item.caseId || !VALID_STATUSES.has(item.status)) {
    throw new Error(`manifest case has invalid id or status: ${JSON.stringify(item)}`);
  }

  const reportPaths = Array.isArray(item.reportPaths) ? item.reportPaths : [];
  const evidences = Array.isArray(item.reportEvidences) ? item.reportEvidences : [];
  const declaredPaths = unique([
    ...reportPaths.filter((value) => typeof value === 'string'),
    ...evidences.map((evidence) => evidence?.path).filter((value) => typeof value === 'string'),
  ]);
  const missingEvidenceFiles = declaredPaths.filter(
    (artifactPath) => !fs.existsSync(resolveArtifact(reportDir, artifactPath)),
  );
  const evidenceKinds = unique(evidences.map((evidence) => evidence?.kind ?? 'unknown'));
  const endpoints = unique(
    evidences.map((evidence) => evidence?.endpoint).filter((value) => typeof value === 'string'),
  );
  const flags = [];

  if (item.status !== 'passed') flags.push('runner_non_pass');
  if (item.status === 'skipped') flags.push('skipped_not_verified');
  if (declaredPaths.length === 0) flags.push('no_declared_evidence');
  if (missingEvidenceFiles.length > 0) flags.push('missing_evidence_file');
  if (evidences.some((evidence) => evidence?.status === 'failure_related')) {
    flags.push('failure_related_evidence');
  }
  if (evidences.some((evidence) => evidence?.status === 'unparsed')) {
    flags.push('unparsed_evidence');
  }
  if (!auditCase) flags.push('missing_ui_audit_case');
  else if (auditCase.screenshotAudit === 'missing') flags.push('missing_screenshot');
  else if (auditCase.screenshotAudit === 'blank') flags.push('blank_screenshot');
  else if (auditCase.screenshotAudit === 'unreadable') flags.push('unreadable_screenshot');

  return {
    caseId: item.caseId,
    name: item.name ?? '',
    status: item.status,
    failureKind: item.failureKind ?? null,
    duration: item.duration ?? null,
    reportPaths,
    evidence: {
      declaredCount: declaredPaths.length,
      kinds: evidenceKinds,
      endpoints,
      missingFiles: missingEvidenceFiles,
      failureRelatedCount: evidences.filter((evidence) => evidence?.status === 'failure_related')
        .length,
      unparsedCount: evidences.filter((evidence) => evidence?.status === 'unparsed').length,
      finalScreenshot: auditCase?.finalScreenshot ?? null,
      screenshotAudit: auditCase?.screenshotAudit ?? 'unknown',
    },
    flags,
  };
}

function buildSummary(selection, caseId) {
  const manifest = readJson(selection.manifestPath, 'manifest');
  if (!Array.isArray(manifest.cases)) throw new Error('manifest.cases must be an array');
  const auditPath = path.join(selection.reportDir, 'ui-audit.json');
  const uiAudit = fs.existsSync(auditPath) ? readJson(auditPath, 'ui-audit') : null;
  const auditCases = new Map(
    Array.isArray(uiAudit?.cases) ? uiAudit.cases.map((item) => [item.caseId, item]) : [],
  );
  let selectedCases = manifest.cases;
  if (caseId) {
    selectedCases = manifest.cases.filter((item) => item.caseId === caseId);
    if (selectedCases.length !== 1) {
      throw new Error(`case must match exactly once; found ${selectedCases.length}: ${caseId}`);
    }
  }
  const cases = selectedCases.map((item) =>
    summarizeCase(selection.reportDir, item, auditCases.get(item.caseId)),
  );
  const counts = { total: cases.length, passed: 0, failed: 0, error: 0, skipped: 0 };
  for (const item of cases) counts[item.status] += 1;

  return {
    schemaVersion: 1,
    reportDir: selection.reportDir,
    manifestPath: selection.manifestPath,
    generatedAt: manifest.generatedAt ?? null,
    counts,
    uiAudit: {
      present: Boolean(uiAudit),
      status: uiAudit?.status ?? null,
    },
    cases,
    guardrail:
      'This output contains deterministic artifact facts only. Inspect visual evidence before assigning targetStatus, businessStatus, root cause, or overall verdict.',
  };
}

function renderText(summary) {
  const lines = [
    '【AI Test 报告事实】',
    `报告：${summary.reportDir}`,
    `生成时间：${summary.generatedAt ?? 'unknown'}`,
    `用例计数：total=${summary.counts.total}, passed=${summary.counts.passed}, failed=${summary.counts.failed}, error=${summary.counts.error}, skipped=${summary.counts.skipped}`,
    `UI 审计：${summary.uiAudit.present ? summary.uiAudit.status : 'missing'}`,
  ];
  for (const item of summary.cases) {
    lines.push(
      '',
      `用例：${item.caseId}`,
      `Runner 状态：${item.status}${item.failureKind ? ` (${item.failureKind})` : ''}`,
      `证据：declared=${item.evidence.declaredCount}, missing=${item.evidence.missingFiles.length}, screenshot=${item.evidence.screenshotAudit}, unparsed=${item.evidence.unparsedCount}`,
      `事实标记：${item.flags.length > 0 ? item.flags.join(', ') : 'none'}`,
    );
    if (item.evidence.missingFiles.length > 0) {
      lines.push(`缺失文件：${item.evidence.missingFiles.join(', ')}`);
    }
  }
  lines.push('', `判定边界：${summary.guardrail}`);
  return lines.join('\n');
}

try {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write(`${helpText()}\n`);
  } else {
    const selection = args.report
      ? resolveExplicitReport(args.report)
      : resolveSinceReport(args.since);
    const summary = buildSummary(selection, args.case);
    process.stdout.write(`${args.json ? JSON.stringify(summary, null, 2) : renderText(summary)}\n`);
  }
} catch (error) {
  fail(error.message);
}
