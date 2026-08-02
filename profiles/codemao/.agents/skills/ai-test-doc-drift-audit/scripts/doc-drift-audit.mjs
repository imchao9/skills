#!/usr/bin/env node

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const CANONICAL_PLATFORM_FALLBACK = ['web', 'computer', 'android', 'ios', 'harmony'];
const IGNORED_CASE_DIRS = new Set(['support', 'templates']);
const PRIORITY_ORDER = new Map([
  ['P0', 0],
  ['P1', 1],
  ['P2', 2],
  ['P3', 3],
]);

export async function auditRepo(repoRoot = process.cwd()) {
  const root = path.resolve(repoRoot);
  const canonicalPlatforms = readCanonicalPlatforms(root);
  const caseProjects = collectCaseProjects(root);
  const configProjects = parseConfigProjects(root);
  const packageScripts = readPackageScripts(root);
  const readme = readText(path.join(root, 'README.md'));
  const readmeTreeProjects = parseReadmeTreeProjects(readme);
  const readmeProjectLists = parseReadmeProjectLists(readme);

  const findings = [];
  findings.push(...compareReadmeTree(readmeTreeProjects, caseProjects));
  findings.push(...compareReadmeMaintainedList(readmeProjectLists, caseProjects));
  findings.push(
    ...scanCommandExamples({
      repoRoot: root,
      file: 'README.md',
      text: readme,
      canonicalPlatforms,
      caseProjects,
      configProjects,
    }),
  );
  findings.push(...scanDeprecatedDocPatterns(root, canonicalPlatforms));

  return {
    repoRoot: root,
    generatedAt: new Date().toISOString(),
    facts: {
      canonicalPlatforms,
      caseProjects: caseProjects.map((entry) => ({
        platform: entry.platform,
        project: entry.project,
        path: entry.relativePath,
        ts: entry.counts.ts,
        yaml: entry.counts.yaml,
        yml: entry.counts.yml,
        formalAssets: entry.formalAssets,
      })),
      configProjects,
      packageScripts,
      readmeTreeProjects,
      readmeProjectLists,
    },
    findings: sortFindings(findings),
  };
}

function readCanonicalPlatforms(root) {
  const platformFile = path.join(root, 'src', 'core', 'platform.ts');
  const text = readText(platformFile);
  const values = new Set();
  for (const match of text.matchAll(/['"]([a-z][a-z0-9-]*)['"]/g)) {
    const value = match[1];
    if (CANONICAL_PLATFORM_FALLBACK.includes(value)) {
      values.add(value);
    }
  }
  return values.size > 0 ? [...values] : [...CANONICAL_PLATFORM_FALLBACK];
}

function collectCaseProjects(root) {
  const casesDir = path.join(root, 'cases');
  if (!existsSync(casesDir)) {
    return [];
  }

  const entries = [];
  for (const platformName of sortedDirNames(casesDir)) {
    if (IGNORED_CASE_DIRS.has(platformName)) {
      continue;
    }
    const platformDir = path.join(casesDir, platformName);
    for (const projectName of sortedDirNames(platformDir)) {
      const projectDir = path.join(platformDir, projectName);
      const counts = countCaseFiles(projectDir);
      entries.push({
        platform: platformName,
        project: projectName,
        absolutePath: projectDir,
        relativePath: path.posix.join('cases', platformName, projectName),
        counts,
        formalAssets: counts.ts + counts.yaml + counts.yml > 0,
      });
    }
  }
  return entries;
}

function parseConfigProjects(root) {
  const configPath = path.join(root, 'midscene.config.ts');
  const text = readText(configPath);
  const projectsBody = extractObjectBodyAfterKey(text, 'projects');
  if (!projectsBody) {
    return [];
  }

  return parseTopLevelObjectEntries(projectsBody).map((entry) => ({
    project: entry.key,
    platforms: parseStringArrayProperty(entry.body, 'platforms'),
  }));
}

function readPackageScripts(root) {
  const packagePath = path.join(root, 'package.json');
  if (!existsSync(packagePath)) {
    return {};
  }
  try {
    const parsed = JSON.parse(readFileSync(packagePath, 'utf8'));
    return parsed.scripts ?? {};
  } catch {
    return {};
  }
}

function parseReadmeTreeProjects(readmeText) {
  const lines = splitLines(readmeText);
  const entries = [];
  let inSection = false;
  let inFence = false;
  let currentPlatform = null;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (/^##\s+当前项目结构\s*$/.test(line)) {
      inSection = true;
      continue;
    }
    if (inSection && /^##\s+/.test(line)) {
      break;
    }
    if (!inSection) {
      continue;
    }
    if (/^\s*```/.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (!inFence) {
      continue;
    }

    const topPlatform = line.match(/^\s*│   (?:├──|└──)\s+(web|computer|android|ios|harmony)\//);
    if (topPlatform) {
      currentPlatform = topPlatform[1];
      continue;
    }
    if (/^\s*│   (?:├──|└──)\s+support\//.test(line)) {
      currentPlatform = null;
      continue;
    }
    const project = line.match(/^\s*│   │   (?:├──|└──)\s+([A-Za-z0-9][\w.-]*)\//);
    if (currentPlatform && project) {
      entries.push({
        platform: currentPlatform,
        project: project[1],
        line: index + 1,
      });
    }
  }

  return entries;
}

function parseReadmeProjectLists(readmeText) {
  const lines = splitLines(readmeText);
  const result = {
    configSupported: [],
    maintainedAssets: [],
  };

  for (const line of lines) {
    if (line.includes('配置层当前支持')) {
      result.configSupported = extractBacktickValuesAfter(line, '配置层当前支持');
    }
    if (line.includes('当前已沉淀正式用例资产')) {
      result.maintainedAssets = extractBacktickValuesAfter(line, '当前已沉淀正式用例资产');
    }
  }

  return result;
}

function compareReadmeTree(readmeTreeProjects, caseProjects) {
  const findings = [];
  const caseDirKeys = new Set(caseProjects.map((entry) => keyFor(entry.platform, entry.project)));
  const treeKeys = new Set(readmeTreeProjects.map((entry) => keyFor(entry.platform, entry.project)));
  const byPlatform = groupProjectsByPlatform(caseProjects);

  for (const entry of readmeTreeProjects) {
    const key = keyFor(entry.platform, entry.project);
    if (caseDirKeys.has(key)) {
      continue;
    }
    findings.push({
      id: `readme-tree-project-without-case-dir:${entry.platform}:${entry.project}`,
      priority: 'P2',
      file: 'README.md',
      line: entry.line,
      stale_claim: `README 项目树列出了 cases/${entry.platform}/${entry.project}/。`,
      current_truth: `当前不存在 cases/${entry.platform}/${entry.project} 目录。当前 cases/${entry.platform} 项目为: ${formatList(
        byPlatform.get(entry.platform) ?? [],
      )}.`,
      why_it_matters: '新同学或 agent 可能会沿着过期项目路径新增或运行用例。',
      suggested_fix: `从 README 目录树移除 cases/${entry.platform}/${entry.project}/；如果该项目确实要恢复，则创建对应目录和正式资产。`,
      verification: `find cases/${entry.platform} -maxdepth 1 -type d | sort`,
    });
  }

  for (const entry of caseProjects) {
    const key = keyFor(entry.platform, entry.project);
    if (treeKeys.has(key)) {
      continue;
    }
    findings.push({
      id: `readme-tree-missing-case-dir:${entry.platform}:${entry.project}`,
      priority: 'P2',
      file: 'README.md',
      stale_claim: `README 项目树没有列出 ${entry.relativePath}/。`,
      current_truth: `当前仓库存在 ${entry.relativePath}/。`,
      why_it_matters: 'README 结构图不再能可靠指引当前活跃用例资产。',
      suggested_fix: `将 ${entry.relativePath}/ 补充到 README 项目树，或说明该目录为什么需要刻意隐藏。`,
      verification: `find cases/${entry.platform} -maxdepth 1 -type d | sort`,
    });
  }

  return findings;
}

function compareReadmeMaintainedList(readmeProjectLists, caseProjects) {
  const findings = [];
  const formalProjects = new Set(
    caseProjects.filter((entry) => entry.formalAssets).map((entry) => entry.project),
  );
  const listedMaintained = new Set(readmeProjectLists.maintainedAssets);

  for (const project of formalProjects) {
    if (listedMaintained.has(project)) {
      continue;
    }
    findings.push({
      id: `readme-maintained-list-missing-project:${project}`,
      priority: 'P2',
      file: 'README.md',
      stale_claim: `README 的正式资产列表遗漏了 ${project}。`,
      current_truth: `${project} 在 cases/ 下已有正式用例资产。`,
      why_it_matters: '上手摘要会低估当前已经沉淀正式可复用用例的项目范围。',
      suggested_fix: `将 \`${project}\` 加入 README “当前已沉淀正式用例资产” 列表；如果这些资产已废弃，则移除对应资产。`,
      verification: `find cases -path '*/${project}/*' -type f \\( -name '*.ts' -o -name '*.yaml' -o -name '*.yml' \\) | sort`,
    });
  }

  for (const project of listedMaintained) {
    if (formalProjects.has(project)) {
      continue;
    }
    findings.push({
      id: `readme-maintained-list-stale-project:${project}`,
      priority: 'P2',
      file: 'README.md',
      stale_claim: `README 的正式资产列表包含了 ${project}。`,
      current_truth: `${project} 在 cases/ 下没有正式 .ts/.yaml/.yml 用例资产。`,
      why_it_matters: 'agent 可能会误以为存在可维护回归套件，但实际只有配置或空目录。',
      suggested_fix: `从 README “当前已沉淀正式用例资产” 列表移除 \`${project}\`，或补充正式 TS 资产。`,
      verification: `find cases -path '*/${project}/*' -type f \\( -name '*.ts' -o -name '*.yaml' -o -name '*.yml' \\) | sort`,
    });
  }

  return findings;
}

function scanCommandExamples({
  file,
  text,
  canonicalPlatforms,
  caseProjects,
  configProjects,
}) {
  const findings = [];
  const formalCaseKeys = new Set(
    caseProjects
      .filter((entry) => entry.formalAssets)
      .map((entry) => keyFor(entry.platform, entry.project)),
  );
  const caseDirKeys = new Set(caseProjects.map((entry) => keyFor(entry.platform, entry.project)));
  const configPlatformKeys = new Set(
    configProjects.flatMap((entry) => entry.platforms.map((platform) => keyFor(platform, entry.project))),
  );
  const canonicalSet = new Set(canonicalPlatforms);

  for (const command of extractCommandRefs(text)) {
    if (command.platform && !canonicalSet.has(command.platform)) {
      findings.push({
        id: `command-noncanonical-platform:${command.platform}:${command.line}`,
        priority: 'P1',
        file,
        line: command.line,
        stale_claim: command.raw,
        current_truth: `当前规范平台只有 ${canonicalPlatforms.join(', ')}。`,
        why_it_matters: '过期平台名会把 agent 带离当前受支持的 runner 契约。',
        suggested_fix: `将 \`${command.platform}\` 替换为正确的规范平台名。`,
        verification: `rg -n "platform[:= ]+${escapeForRegex(command.platform)}|TEST_PLATFORM=${escapeForRegex(
          command.platform,
        )}" ${file}`,
      });
    }

    if (!command.platform || !command.project || !canonicalSet.has(command.platform)) {
      continue;
    }

    const commandKey = keyFor(command.platform, command.project);
    if (formalCaseKeys.has(commandKey)) {
      continue;
    }

    const projectIsConfiguredForPlatform = configPlatformKeys.has(commandKey);
    const projectDirExists = caseDirKeys.has(commandKey);
    if (projectIsConfiguredForPlatform || projectDirExists) {
      findings.push({
        id: `readme-command-config-only-project:${command.platform}:${command.project}`,
        priority: 'P2',
        file,
        line: command.line,
        stale_claim: command.raw,
        current_truth: `${command.project} 已配置或存在于 ${command.platform}，但 cases/${command.platform}/${command.project} 下没有正式用例资产。`,
        why_it_matters: '常用命令通常应该指向可维护、可运行的套件，而不是仅配置支持或空目录项目。',
        suggested_fix: `将示例改为有正式资产的项目，或明确标注 \`${command.project}\` 只是 config-only / setup-only。`,
        verification: `find cases/${command.platform}/${command.project} -type f \\( -name '*.ts' -o -name '*.yaml' -o -name '*.yml' \\) 2>/dev/null | sort`,
      });
      continue;
    }

    findings.push({
      id: `readme-command-unknown-project:${command.platform}:${command.project}`,
      priority: 'P2',
      file,
      line: command.line,
      stale_claim: command.raw,
      current_truth: `没有找到 cases/${command.platform}/${command.project} 目录，也没有找到匹配的 midscene.config.ts 项目/平台配置。`,
      why_it_matters: '该命令无法把 agent 指向可维护项目或已配置的运行目标。',
      suggested_fix: `将 \`${command.project}\` 替换为现有维护项目，补充缺失配置/用例资产，或移除该命令。`,
      verification: `find cases/${command.platform} -maxdepth 1 -type d | sort && rg -n "${escapeForRegex(
        command.project,
      )}" midscene.config.ts`,
    });
  }

  return findings;
}

function scanDeprecatedDocPatterns(root, canonicalPlatforms) {
  const findings = [];
  const files = collectDocFiles(root, ['README.md', 'AGENTS.md', 'docs', '.agents/skills']).filter(
    (file) => !file.startsWith('.agents/skills/ai-test-doc-drift-audit/'),
  );
  const patterns = [
    {
      id: 'deprecated-type-h5',
      regex: /\btype:\s*h5\b/,
      priority: 'P1',
      why: '新的正式示例必须使用规范平台名和 TS 用例。',
      fix: '将 type: h5 替换为 type: web 等规范平台，或移除历史 YAML 示例。',
    },
    {
      id: 'deprecated-platform-h5',
      regex: /\bplatform:\s*h5\b/,
      priority: 'P1',
      why: 'h5 不是当前仓库的规范平台名。',
      fix: '将 platform: h5 替换为 platform: web。',
    },
    {
      id: 'deprecated-platform-pc',
      regex: /\bplatform:\s*pc\b/,
      priority: 'P1',
      why: 'pc 在这里是产品/领域称呼，不是规范平台名。',
      fix: '如果指桌面 runner，将 platform: pc 替换为 platform: computer。',
    },
    {
      id: 'deprecated-platform-desktop',
      regex: /\bplatform:\s*desktop\b/,
      priority: 'P1',
      why: 'desktop/ 是目录和产品入口，规范平台名是 computer。',
      fix: '如果指 runner 平台，将 platform: desktop 替换为 platform: computer。',
    },
    {
      id: 'stale-sealos-section',
      regex: /Sealos Web 回归分批执行/,
      priority: 'P2',
      why: '这段更像历史业务上下文，不像当前通用 README 指引。',
      fix: '从 README 删除；如果仍有历史参考价值，则移动到 knowledge。',
    },
    {
      id: 'stale-runtime-fallback-wording',
      regex: /runtime fallback only/i,
      priority: 'P2',
      why: 'coding-agent 处理 QA 转换时，不应在 GUI runtime fallback 处作为完成态，除非用户明确要求一次性临时报告。',
      fix: '收紧表述为正式 TS 资产、explicit skip、blocker，或用户明确要求的一次性 transient run。',
    },
    {
      id: 'yaml-ts-dual-default',
      regex: /YAML\s*\/\s*TS 用例/,
      priority: 'P2',
      why: '当前正式生成业务用例的规则是 TS-first。',
      fix: '改写为默认 TypeScript ScriptTestCase，并将 YAML 限定为显式历史/手写场景。',
    },
  ];

  for (const docFile of files) {
    const text = readText(path.join(root, docFile));
    const lines = splitLines(text);
    for (let index = 0; index < lines.length; index += 1) {
      const line = lines[index];
      for (const pattern of patterns) {
        if (!pattern.regex.test(line)) {
          continue;
        }
        findings.push({
          id: `${pattern.id}:${docFile}:${index + 1}`,
          priority: pattern.priority,
          file: docFile,
          line: index + 1,
          stale_claim: line.trim(),
          current_truth: `当前规范平台只有 ${canonicalPlatforms.join(
            ', ',
          )}；正式生成用例默认使用 TypeScript ScriptTestCase。`,
          why_it_matters: pattern.why,
          suggested_fix: pattern.fix,
          verification: `rg -n "${pattern.regex.source}" ${docFile}`,
        });
      }
    }
  }

  return findings;
}

function extractCommandRefs(text) {
  const commands = [];
  const lines = splitLines(text);
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    const envPlatform = line.match(/\bTEST_PLATFORM=([A-Za-z0-9_-]+)/);
    const envProject = line.match(/\bTEST_PROJECT=([A-Za-z0-9_-]+)/);
    const cliPlatform = line.match(/\s--platform\s+([A-Za-z0-9_-]+)/);
    const cliProject = line.match(/\s--project\s+([A-Za-z0-9_-]+)/);
    const platform = envPlatform?.[1] ?? cliPlatform?.[1];
    const project = envProject?.[1] ?? cliProject?.[1];
    if (!platform && !project) {
      continue;
    }
    commands.push({
      platform,
      project,
      line: index + 1,
      raw: line.trim(),
    });
  }
  return commands;
}

function parseTopLevelObjectEntries(body) {
  const entries = [];
  let index = 0;
  while (index < body.length) {
    index = skipWhitespaceAndCommas(body, index);
    const keyResult = readObjectKey(body, index);
    if (!keyResult) {
      index += 1;
      continue;
    }
    index = skipWhitespace(body, keyResult.end);
    if (body[index] !== ':') {
      index += 1;
      continue;
    }
    index = skipWhitespace(body, index + 1);
    if (body[index] !== '{') {
      index += 1;
      continue;
    }
    const end = findMatchingBrace(body, index);
    if (end === -1) {
      break;
    }
    entries.push({
      key: keyResult.key,
      body: body.slice(index + 1, end),
    });
    index = end + 1;
  }
  return entries;
}

function extractObjectBodyAfterKey(text, key) {
  const keyIndex = text.indexOf(`${key}:`);
  if (keyIndex === -1) {
    return '';
  }
  const braceStart = text.indexOf('{', keyIndex);
  if (braceStart === -1) {
    return '';
  }
  const braceEnd = findMatchingBrace(text, braceStart);
  if (braceEnd === -1) {
    return '';
  }
  return text.slice(braceStart + 1, braceEnd);
}

function findMatchingBrace(text, start) {
  let depth = 0;
  let quote = null;
  let escape = false;
  let lineComment = false;
  let blockComment = false;

  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (lineComment) {
      if (char === '\n') {
        lineComment = false;
      }
      continue;
    }
    if (blockComment) {
      if (char === '*' && next === '/') {
        blockComment = false;
        index += 1;
      }
      continue;
    }
    if (quote) {
      if (escape) {
        escape = false;
        continue;
      }
      if (char === '\\') {
        escape = true;
        continue;
      }
      if (char === quote) {
        quote = null;
      }
      continue;
    }
    if (char === '/' && next === '/') {
      lineComment = true;
      index += 1;
      continue;
    }
    if (char === '/' && next === '*') {
      blockComment = true;
      index += 1;
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
      continue;
    }
    if (char === '{') {
      depth += 1;
      continue;
    }
    if (char === '}') {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
  }

  return -1;
}

function readObjectKey(text, start) {
  const char = text[start];
  if (char === '"' || char === "'") {
    let index = start + 1;
    let value = '';
    while (index < text.length && text[index] !== char) {
      value += text[index];
      index += 1;
    }
    return { key: value, end: index + 1 };
  }

  const match = text.slice(start).match(/^([A-Za-z_$][\w$-]*)/);
  if (!match) {
    return null;
  }
  return { key: match[1], end: start + match[1].length };
}

function parseStringArrayProperty(body, propertyName) {
  const match = body.match(new RegExp(`${propertyName}\\s*:\\s*\\[([\\s\\S]*?)\\]`));
  if (!match) {
    return [];
  }
  return [...match[1].matchAll(/['"]([^'"]+)['"]/g)].map((entry) => entry[1]);
}

function countCaseFiles(projectDir) {
  const counts = { ts: 0, yaml: 0, yml: 0 };
  for (const filePath of walkFiles(projectDir)) {
    if (filePath.endsWith('.ts')) {
      counts.ts += 1;
    } else if (filePath.endsWith('.yaml')) {
      counts.yaml += 1;
    } else if (filePath.endsWith('.yml')) {
      counts.yml += 1;
    }
  }
  return counts;
}

function collectDocFiles(root, relativeRoots) {
  const files = [];
  for (const relativeRoot of relativeRoots) {
    const absolute = path.join(root, relativeRoot);
    if (!existsSync(absolute)) {
      continue;
    }
    const stats = statSync(absolute);
    if (stats.isFile()) {
      files.push(relativeRoot);
      continue;
    }
    for (const filePath of walkFiles(absolute)) {
      if (!/\.(md|ts|yaml|yml|json)$/i.test(filePath)) {
        continue;
      }
      files.push(path.relative(root, filePath).split(path.sep).join(path.posix.sep));
    }
  }
  return files.sort();
}

function walkFiles(dir) {
  if (!existsSync(dir)) {
    return [];
  }
  const results = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === 'node_modules' || entry.name === '.git') {
      continue;
    }
    const entryPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkFiles(entryPath));
    } else if (entry.isFile()) {
      results.push(entryPath);
    }
  }
  return results;
}

function sortedDirNames(dir) {
  if (!existsSync(dir)) {
    return [];
  }
  return readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b));
}

function extractBacktickValuesAfter(line, marker) {
  const markerIndex = line.indexOf(marker);
  if (markerIndex === -1) {
    return [];
  }
  return [...line.slice(markerIndex).matchAll(/`([^`]+)`/g)].map((entry) => entry[1]);
}

function groupProjectsByPlatform(caseProjects) {
  const grouped = new Map();
  for (const entry of caseProjects) {
    const list = grouped.get(entry.platform) ?? [];
    list.push(entry.project);
    grouped.set(entry.platform, list);
  }
  for (const list of grouped.values()) {
    list.sort((a, b) => a.localeCompare(b));
  }
  return grouped;
}

function sortFindings(findings) {
  return findings.sort((left, right) => {
    const priorityDelta =
      (PRIORITY_ORDER.get(left.priority) ?? 99) - (PRIORITY_ORDER.get(right.priority) ?? 99);
    if (priorityDelta !== 0) {
      return priorityDelta;
    }
    return left.id.localeCompare(right.id);
  });
}

function splitLines(text) {
  return text.split(/\r?\n/);
}

function readText(filePath) {
  if (!existsSync(filePath)) {
    return '';
  }
  return readFileSync(filePath, 'utf8');
}

function skipWhitespace(text, index) {
  let cursor = index;
  while (cursor < text.length && /\s/.test(text[cursor])) {
    cursor += 1;
  }
  return cursor;
}

function skipWhitespaceAndCommas(text, index) {
  let cursor = index;
  while (cursor < text.length && /[\s,]/.test(text[cursor])) {
    cursor += 1;
  }
  return cursor;
}

function keyFor(platform, project) {
  return `${platform}:${project}`;
}

function formatList(values) {
  return values.length > 0 ? values.join(', ') : '(none)';
}

function escapeForRegex(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function renderMarkdown(result) {
  const lines = [
    '# 文档漂移审计',
    '',
    `- 仓库: ${result.repoRoot}`,
    `- 生成时间: ${result.generatedAt}`,
    `- 发现数量: ${result.findings.length}`,
    '',
    '## 事实摘要',
    '',
    `- 规范平台: ${result.facts.canonicalPlatforms.join(', ')}`,
    `- 用例项目目录: ${result.facts.caseProjects
      .map((entry) => `${entry.platform}/${entry.project}`)
      .join(', ')}`,
    `- 配置项目: ${result.facts.configProjects
      .map((entry) => `${entry.project}(${entry.platforms.join('|') || 'no-platform'})`)
      .join(', ')}`,
    '',
    '## 问题列表',
    '',
  ];

  if (result.findings.length === 0) {
    lines.push('未发现确定性的文档漂移。');
    return `${lines.join('\n')}\n`;
  }

  for (const finding of result.findings) {
    lines.push(`### ${finding.priority} ${finding.id}`);
    if (finding.file) {
      lines.push(`- 位置: ${finding.file}${finding.line ? `:${finding.line}` : ''}`);
    }
    lines.push(`- 过期声明: ${finding.stale_claim ?? '无'}`);
    lines.push(`- 当前事实: ${finding.current_truth ?? '无'}`);
    lines.push(`- 为什么重要: ${finding.why_it_matters ?? '无'}`);
    lines.push(`- 建议修复: ${finding.suggested_fix ?? '无'}`);
    lines.push(`- 验证命令: \`${finding.verification ?? '人工复核'}\``);
    lines.push('');
  }

  return lines.join('\n');
}

function parseArgs(argv) {
  const args = {
    root: process.cwd(),
    format: 'markdown',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--json') {
      args.format = 'json';
      continue;
    }
    if (arg === '--markdown') {
      args.format = 'markdown';
      continue;
    }
    if (arg === '--format') {
      args.format = argv[index + 1] ?? args.format;
      index += 1;
      continue;
    }
    if (arg === '--root') {
      args.root = argv[index + 1] ?? args.root;
      index += 1;
      continue;
    }
    if (!arg.startsWith('-')) {
      args.root = arg;
    }
  }

  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = await auditRepo(args.root);
  if (args.format === 'json') {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    return;
  }
  process.stdout.write(renderMarkdown(result));
}

const currentFile = fileURLToPath(import.meta.url);
const invokedFile = process.argv[1] ? fileURLToPath(pathToFileURL(process.argv[1])) : '';
if (currentFile === invokedFile) {
  main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
