#!/usr/bin/env node
'use strict';

const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');

const DEFAULT_BASE_URL = 'https://crp.codemao.cn';
const SKILL_ROOT = path.resolve(__dirname, '..');
const OUTPUT_DIR = path.join(SKILL_ROOT, 'output');
const DEFAULT_STORAGE_STATE = path.join(OUTPUT_DIR, 'auth-storage-state.json');
const DEFAULT_AUTH_FILE = path.join(OUTPUT_DIR, 'auth-cookie.txt');
const PLAYWRIGHT_OPEN_TIMEOUT_MS = 30000;
const REQUIRED_AUTH_COOKIE_NAMES = new Set(['internal_account_token', 'admin-authorization']);
const DINGTALK_LOGIN_ORIGIN = 'https://login.dingtalk.com';

async function grantDingTalkLocalNetworkAccess(context) {
  try {
    await context.grantPermissions(['local-network-access'], { origin: DINGTALK_LOGIN_ORIGIN });
    return true;
  } catch (error) {
    return false;
  }
}

function parseArgs(argv) {
  const args = {
    baseUrl: DEFAULT_BASE_URL,
    storageState: DEFAULT_STORAGE_STATE,
    authFile: DEFAULT_AUTH_FILE,
    loginUrl: '',
    loginTimeout: 180,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--base-url') { args.baseUrl = value; i += 1; continue; }
    if (key === '--storage-state') { args.storageState = value; i += 1; continue; }
    if (key === '--auth-file') { args.authFile = value; i += 1; continue; }
    if (key === '--login-url') { args.loginUrl = value; i += 1; continue; }
    if (key === '--login-timeout') { args.loginTimeout = Number(value); i += 1; continue; }
    if (key === '-h' || key === '--help') {
      console.log('usage: node scripts/auth-login.js [--base-url URL] [--storage-state PATH] [--auth-file PATH] [--login-url URL] [--login-timeout SECONDS]');
      process.exit(0);
    }
    throw new Error(`unknown argument: ${key}`);
  }
  args.baseUrl = args.baseUrl.replace(/\/$/, '');
  args.targetUrl = args.loginUrl || `${args.baseUrl}/workbench`;
  return args;
}

function resolveInstalledPlaywrightModulePath() {
  try {
    const packagePath = require.resolve('playwright/package.json', {
      paths: [process.cwd(), SKILL_ROOT, __dirname],
    });
    return path.dirname(packagePath);
  } catch (error) {
    return null;
  }
}

async function findNpxPlaywrightModulePath() {
  const root = path.join(os.homedir(), '.npm', '_npx');
  const entries = await fs.readdir(root, { withFileTypes: true }).catch(() => []);
  const candidates = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const packagePath = path.join(root, entry.name, 'node_modules', 'playwright', 'package.json');
    try {
      const stat = await fs.stat(packagePath);
      candidates.push({ packagePath, mtimeMs: stat.mtimeMs });
    } catch (error) {
    }
  }
  candidates.sort((a, b) => b.mtimeMs - a.mtimeMs);
  return candidates.length ? path.dirname(candidates[0].packagePath) : null;
}

async function resolvePlaywrightModulePath() {
  const installedPath = resolveInstalledPlaywrightModulePath();
  if (installedPath) return installedPath;

  const npxPath = await findNpxPlaywrightModulePath();
  if (npxPath) return npxPath;

  throw new Error('Playwright library package not found. Install playwright, run npx playwright once, or use manual cookie mode.');
}

function isCrpCookie(cookie) {
  const domain = String(cookie.domain || '');
  return domain === 'crp.codemao.cn' || domain.endsWith('.codemao.cn');
}

function buildCookieHeader(cookies) {
  return cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join('; ');
}

function hasRequiredCookies(cookies) {
  const names = new Set(cookies.map((cookie) => String(cookie.name || '')));
  return Array.from(REQUIRED_AUTH_COOKIE_NAMES).every((name) => names.has(name));
}

async function writeAuthFiles(args, cookies) {
  const crpCookies = cookies.filter(isCrpCookie);
  if (!hasRequiredCookies(crpCookies)) {
    throw new Error('required auth cookies are missing');
  }
  const cookieHeader = buildCookieHeader(crpCookies);
  await fs.mkdir(path.dirname(args.storageState), { recursive: true });
  await fs.mkdir(path.dirname(args.authFile), { recursive: true });
  await fs.writeFile(args.storageState, `${JSON.stringify({ cookies: crpCookies, origins: [] }, null, 2)}\n`, 'utf8');
  const generatedAt = new Date().toISOString();
  const cookieNames = crpCookies.map((cookie) => cookie.name).join(', ');
  await fs.writeFile(args.authFile, [
    '# auth cookie file',
    `# base_url: ${args.baseUrl}`,
    `# generated_at: ${generatedAt}`,
    '# source: playwright-node-auth-login',
    `# storage_state_path: ${args.storageState}`,
    `# cookie_names: ${cookieNames}`,
    '# 直接覆盖最后一行即可更新 cookie。',
    cookieHeader,
    '',
  ].join('\n'), 'utf8');
  return {
    base_url: args.baseUrl,
    generated_at: generatedAt,
    source: 'playwright-node-auth-login',
    storage_state_path: args.storageState,
    auth_file_path: args.authFile,
    cookie_count: crpCookies.length,
    cookie_names: crpCookies.map((cookie) => cookie.name),
    has_required_auth_cookies: true,
    missing_required_auth_cookies: [],
  };
}

async function runLogin(args) {
  const playwrightModulePath = await resolvePlaywrightModulePath();
  const { chromium } = require(playwrightModulePath);
  const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), 'crp-deploy-auth-login-'));
  const profileDir = path.join(userDataDir, 'profile');
  const context = await chromium.launchPersistentContext(profileDir, {
    channel: 'chrome',
    headless: false,
  });
  await grantDingTalkLocalNetworkAccess(context);
  let settled = false;
  let pageCount = 0;
  let timeoutId;
  let settleResolve;
  let settleReject;
  const settledPromise = new Promise((resolve, reject) => {
    settleResolve = resolve;
    settleReject = reject;
  });

  function settleSuccess(payload) {
    if (settled) return;
    settled = true;
    if (timeoutId) clearTimeout(timeoutId);
    settleResolve(payload);
  }
  function settleError(error) {
    if (settled) return;
    settled = true;
    if (timeoutId) clearTimeout(timeoutId);
    settleReject(error);
  }
  function markPage(page) {
    pageCount += 1;
    page.once('close', () => {
      pageCount = Math.max(0, pageCount - 1);
      if (pageCount === 0) settleError(new Error('登录已取消或浏览器已关闭，auth-login 已停止。'));
    });
  }

  try {
    context.once('close', () => settleError(new Error('登录已取消或浏览器已关闭，auth-login 已停止。')));
    const browser = context.browser();
    if (browser) browser.once('disconnected', () => settleError(new Error('登录已取消或浏览器已关闭，auth-login 已停止。')));
    for (const page of context.pages()) markPage(page);
    context.on('page', markPage);
    context.on('response', async (response) => {
      if (settled) return;
      try {
        const url = response.url();
        if (!url.startsWith(`${args.baseUrl}/api/my/assigned_requirements`)) return;
        if (!response.ok()) return;
        const headers = response.headers();
        const contentType = String(headers['content-type'] || headers['Content-Type'] || '');
        if (!contentType.includes('application/json')) return;
        const payload = await response.json().catch(() => null);
        if (!payload || !Array.isArray(payload.data)) return;
        const cookies = (await context.cookies()).filter(isCrpCookie);
        await writeAuthFiles(args, cookies);
        console.log(JSON.stringify({step: 'auth-login-success', cookie_count: cookies.length}));
        settleSuccess({ cookies });
        await context.close().catch(() => {});
      } catch (error) {
        settleError(error);
      }
    });
    const page = context.pages()[0] || await context.newPage();
    if (pageCount === 0) markPage(page);
    timeoutId = setTimeout(() => settleError(new Error('登录等待超时，auth-login 已停止。')), Math.max(1, args.loginTimeout) * 1000);
    await page.goto(args.targetUrl, { timeout: PLAYWRIGHT_OPEN_TIMEOUT_MS, waitUntil: 'domcontentloaded' }).catch(() => {});
    console.log(JSON.stringify({step: 'auth-login-opened', timeout: `${args.loginTimeout}s`}));
    await settledPromise;
  } finally {
    await context.close().catch(() => {});
    await fs.rm(userDataDir, { recursive: true, force: true }).catch(() => {});
  }
}

if (require.main === module) {
  (async () => {
    const args = parseArgs(process.argv.slice(2));
    await runLogin(args);
  })().catch((error) => {
    console.error(`ERROR: ${error && error.message ? error.message : String(error)}`);
    process.exit(1);
  });
}

module.exports = { grantDingTalkLocalNetworkAccess };
