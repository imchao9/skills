#!/usr/bin/env node

import 'dotenv/config';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, '../../../..');
const bridgePath = path.join(projectRoot, 'desktop/bridge.ts');
const SECRET_KEYS = new Set([
  'FIGMA_ACCESS_TOKEN',
  'MIDSCENE_MODEL_API_KEY',
  'MIDSCENE_PLANNING_MODEL_API_KEY',
  'MIDSCENE_INSIGHT_MODEL_API_KEY',
  'OPENAI_API_KEY',
]);
const ENV_KEYS = [
  ...SECRET_KEYS,
  'MIDSCENE_MODEL_BASE_URL',
  'MIDSCENE_MODEL_NAME',
  'MIDSCENE_MODEL_FAMILY',
  'MIDSCENE_PLANNING_MODEL_BASE_URL',
  'MIDSCENE_PLANNING_MODEL_NAME',
  'MIDSCENE_PLANNING_MODEL_FAMILY',
  'MIDSCENE_INSIGHT_MODEL_BASE_URL',
  'MIDSCENE_INSIGHT_MODEL_NAME',
  'MIDSCENE_INSIGHT_MODEL_FAMILY',
  'OPENAI_BASE_URL',
  'ELECTRON_APP_PATH',
  'LOGIN_ACCOUNT',
  'LOGIN_PHONE',
  'LOGIN_PASSWORD',
  'RUN_TIMEOUT_MS',
  'AIT_CASE_TIMEOUT_MS',
  'CACHE_STRATEGY',
  'HEADLESS',
  'MAX_CONCURRENCY',
];
const REVIEW_STATUSES = new Set([
  'DESIGN_REVIEW_PASSED',
  'DESIGN_REVIEW_ADJUST',
  'DESIGN_REVIEW_NEEDS_REVIEW',
  'DESIGN_REVIEW_UNKNOWN',
]);

function parseArgs(argv) {
  const [command, ...rest] = argv;
  if (!['list', 'preflight', 'run'].includes(command)) {
    throw new Error(`expected command list, preflight, or run; received ${command ?? 'none'}`);
  }
  const options = { command };
  for (let index = 0; index < rest.length; index += 1) {
    const arg = rest[index];
    const keyMap = {
      '--case': 'caseId',
      '--package-name': 'packageName',
      '--course-name': 'courseName',
      '--link-name': 'linkName',
      '--notes': 'notes',
      '--expected-variance': 'expectedVariance',
      '--viewport': 'viewport',
    };
    const key = keyMap[arg];
    if (!key) throw new Error(`unsupported argument: ${arg}`);
    const value = rest[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`${arg} requires a value`);
    options[key] = value;
    index += 1;
  }
  if (command !== 'list' && !options.caseId) throw new Error(`${command} requires --case`);
  if (command === 'list' && rest.length > 0) throw new Error('list does not accept options');
  return options;
}

function collectEnv() {
  return Object.fromEntries(
    ENV_KEYS.map((key) => [key, process.env[key]])
      .filter(([, value]) => typeof value === 'string' && value.trim())
      .map(([key, value]) => [key, value.trim()]),
  );
}

function sanitizeObject(value) {
  if (Array.isArray(value)) return value.map(sanitizeObject);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !SECRET_KEYS.has(key))
      .map(([key, child]) => [key, sanitizeObject(child)]),
  );
}

function sanitizeLine(line, secretValues) {
  const trimmed = line.trim();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
    try {
      return JSON.stringify(sanitizeObject(JSON.parse(trimmed)));
    } catch {
      // Fall through to literal filtering for non-JSON log lines.
    }
  }
  let result = line;
  for (const secret of secretValues) {
    if (secret) result = result.split(secret).join('[REDACTED]');
  }
  return result;
}

function createLineSink(stream, output, secretValues, collected) {
  let buffer = '';
  stream.setEncoding('utf8');
  stream.on('data', (chunk) => {
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      collected.push(line);
      output.write(`${sanitizeLine(line, secretValues)}\n`);
    }
  });
  return () => {
    if (!buffer) return;
    collected.push(buffer);
    output.write(`${sanitizeLine(buffer, secretValues)}\n`);
  };
}

async function runBridge(command, payloadPath, secretValues, forward = true) {
  const child = spawn(process.execPath, ['--import', 'tsx', bridgePath, command, payloadPath], {
    cwd: projectRoot,
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  const stdoutLines = [];
  const stderrLines = [];
  const stdoutTarget = forward ? process.stdout : { write() {} };
  const stderrTarget = forward ? process.stderr : { write() {} };
  const flushStdout = createLineSink(child.stdout, stdoutTarget, secretValues, stdoutLines);
  const flushStderr = createLineSink(child.stderr, stderrTarget, secretValues, stderrLines);

  const signalHandler = (signal) => {
    child.kill(signal);
  };
  process.once('SIGINT', signalHandler);
  process.once('SIGTERM', signalHandler);
  const exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code, signal) => resolve(code ?? (signal ? 1 : 0)));
  });
  process.removeListener('SIGINT', signalHandler);
  process.removeListener('SIGTERM', signalHandler);
  flushStdout();
  flushStderr();
  return { exitCode, stdoutLines, stderrLines };
}

function lastJson(lines) {
  for (const line of [...lines].reverse()) {
    try {
      return JSON.parse(line);
    } catch {
      // Continue past progress logs.
    }
  }
  return undefined;
}

function parseViewport(value) {
  if (!value) return undefined;
  const match = value.match(/^(\d+)x(\d+)$/i);
  if (!match) throw new Error('--viewport must use <width>x<height>');
  const width = Number(match[1]);
  const height = Number(match[2]);
  if (width <= 0 || height <= 0) throw new Error('--viewport dimensions must be positive');
  return { width, height };
}

function writePayload(payloadPath, payload) {
  fs.writeFileSync(payloadPath, `${JSON.stringify(payload, null, 2)}\n`, {
    encoding: 'utf8',
    mode: 0o600,
  });
  fs.chmodSync(payloadPath, 0o600);
}

function artifactExists(reportDir, artifactPath) {
  if (!artifactPath) return false;
  const resolved = path.isAbsolute(artifactPath)
    ? artifactPath
    : path.join(reportDir, artifactPath);
  return fs.existsSync(resolved);
}

function inspectAcceptance(reportDirInput, caseId) {
  const reportDir = path.resolve(projectRoot, reportDirInput);
  const requiredFiles = [
    'manifest.json',
    'ui-audit.json',
    'design-walkthrough-input.json',
    'design-spec.json',
    'design-walkthrough.json',
    'index.html',
  ];
  const issues = requiredFiles
    .filter((fileName) => !fs.existsSync(path.join(reportDir, fileName)))
    .map((fileName) => `missing artifact: ${fileName}`);
  let caseResult;
  let designResult;

  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(reportDir, 'manifest.json'), 'utf8'));
    caseResult = manifest.cases?.find((item) => item.caseId === caseId);
    if (!caseResult) issues.push(`manifest case not found: ${caseId}`);
    else if (caseResult.status !== 'passed') {
      issues.push(`formal case status is ${caseResult.status}`);
    }
    const screenshot = caseResult?.reportEvidences?.find(
      (evidence) => evidence.kind === 'screenshot',
    );
    if (!screenshot || !artifactExists(reportDir, screenshot.path)) {
      issues.push('final screenshot evidence is missing');
    }
  } catch (error) {
    issues.push(`manifest unreadable: ${error.message}`);
  }

  try {
    designResult = JSON.parse(
      fs.readFileSync(path.join(reportDir, 'design-walkthrough.json'), 'utf8'),
    );
    if (designResult.target?.targetReached !== true) issues.push('target state was not reached');
    if (!REVIEW_STATUSES.has(designResult.verdict?.status)) {
      issues.push('overall design verdict is missing or invalid');
    } else if (designResult.verdict.status === 'DESIGN_REVIEW_UNKNOWN') {
      issues.push('overall design verdict is unknown');
    }
  } catch (error) {
    issues.push(`design result unreadable: ${error.message}`);
  }

  const checkpoints = Array.isArray(designResult?.report?.checkpoints)
    ? designResult.report.checkpoints
    : [];
  return {
    event: 'design-walkthrough-acceptance',
    workflowComplete: issues.length === 0,
    reportDir,
    caseId,
    executionStatus: caseResult?.status ?? 'unknown',
    targetReached: designResult?.target?.targetReached ?? false,
    reviewStatus: designResult?.verdict?.status ?? 'unknown',
    unknownCheckpointCount: checkpoints.filter(
      (checkpoint) => checkpoint.status === 'DESIGN_REVIEW_UNKNOWN',
    ).length,
    issues,
  };
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const tempBase = process.env.AIT_SKILL_TEMP_ROOT
    ? path.resolve(process.env.AIT_SKILL_TEMP_ROOT)
    : os.tmpdir();
  fs.mkdirSync(tempBase, { recursive: true });
  const tempDir = fs.mkdtempSync(path.join(tempBase, 'ai-test-design-walkthrough-'));
  const payloadPath = path.join(tempDir, 'payload.json');
  let exitCode = 0;

  const cleanup = () => fs.rmSync(tempDir, { recursive: true, force: true });
  process.once('exit', cleanup);
  process.once('SIGINT', cleanup);
  process.once('SIGTERM', cleanup);
  try {
    writePayload(payloadPath, {});
    const listed = await runBridge('design-list', payloadPath, [], false);
    if (listed.exitCode !== 0) {
      throw new Error(listed.stderrLines.join('\n') || 'design-list failed');
    }
    const listResult = lastJson(listed.stdoutLines);
    if (!Array.isArray(listResult?.cases)) throw new Error('design-list returned no cases');
    if (options.command === 'list') {
      process.stdout.write(`${JSON.stringify(sanitizeObject(listResult))}\n`);
      return;
    }

    const registration = listResult.cases.find((item) => item.caseId === options.caseId);
    if (!registration) throw new Error(`registered design case not found: ${options.caseId}`);
    const env = collectEnv();
    if (options.command === 'preflight' && !env.MIDSCENE_MODEL_API_KEY) {
      env.MIDSCENE_MODEL_BASE_URL ??= 'https://preflight.invalid/v1';
      env.MIDSCENE_MODEL_NAME ??= 'preflight-placeholder';
      env.MIDSCENE_MODEL_FAMILY ??= 'openai';
    }
    const payload = {
      mode: 'design-walkthrough',
      caseId: registration.caseId,
      figmaUrl: registration.figmaUrl,
      nodeId: registration.nodeId,
      data: {
        packageName: options.packageName ?? registration.dataDefaults?.packageName,
        courseName: options.courseName ?? registration.dataDefaults?.courseName,
        linkName: options.linkName ?? registration.dataDefaults?.linkName,
      },
      ...(options.notes ? { notes: options.notes } : {}),
      ...(options.expectedVariance ? { expectedVariance: options.expectedVariance } : {}),
      ...(options.viewport ? { viewport: parseViewport(options.viewport) } : {}),
      env,
    };
    writePayload(payloadPath, payload);
    const secretValues = [...SECRET_KEYS].map((key) => env[key]).filter(Boolean);
    const bridgeCommand = options.command === 'preflight' ? 'design-preflight' : 'design-run';
    const result = await runBridge(bridgeCommand, payloadPath, secretValues);
    exitCode = result.exitCode;

    if (exitCode === 0 && options.command === 'preflight') {
      const preflight = lastJson(result.stdoutLines);
      if (!preflight?.ok) exitCode = 2;
    }
    if (exitCode === 0 && options.command === 'run') {
      const done = [...result.stdoutLines]
        .map((line) => {
          try {
            return JSON.parse(line);
          } catch {
            return undefined;
          }
        })
        .findLast((item) => item?.event === 'done');
      if (!done?.result?.reportDir) {
        throw new Error('design-run completed without a report directory');
      }
      const acceptance = inspectAcceptance(done.result.reportDir, options.caseId);
      process.stdout.write(`${JSON.stringify(acceptance)}\n`);
      if (!acceptance.workflowComplete) exitCode = 3;
    }
  } finally {
    cleanup();
    process.removeListener('exit', cleanup);
    process.removeListener('SIGINT', cleanup);
    process.removeListener('SIGTERM', cleanup);
  }
  process.exitCode = exitCode;
}

const isDirectRun =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isDirectRun) {
  main().catch((error) => {
    process.stderr.write(`ai-test-design-walkthrough: ${error.message}\n`);
    process.exitCode = 1;
  });
}

export { inspectAcceptance };
