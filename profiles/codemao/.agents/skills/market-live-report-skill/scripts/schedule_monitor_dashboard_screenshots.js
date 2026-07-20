#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const { parseText } = require("./parse_live_report");
const {
  CdpWebSocket,
  closeBrowser,
  launchBrowser,
  waitForPageWebSocket,
  sleep,
} = require("./login_live_stream_cookie");

const DEFAULT_MILESTONES = [15, 20, 30];
const DEFAULT_GRAFANA_OVERVIEW_URL =
  "https://grafana.codemao.cn/d/SpSQKcpMl13/ying-xiao-zhi-bo-overviews?orgId=1&refresh=30s";
const DEFAULT_DASHBOARD_URL = DEFAULT_GRAFANA_OVERVIEW_URL;
const DEFAULT_TARGET_TEXT = "营销直播Overviews";
const DEFAULT_TARGET_HREF = DEFAULT_GRAFANA_OVERVIEW_URL;
const DEFAULT_OUTPUT_DIR = path.resolve(__dirname, "../output/duty-docs/assets");
const DEFAULT_SCREENSHOT_SECTIONS = [
  {
    id: "overview",
    label: "顶部概览",
    anchors: [],
  },
  {
    id: "microservice-pod-curves",
    label: "微服务与Pod资源曲线图",
    anchors: ["微服务与Pod资源曲线图"],
    fallbackRatio: 0.45,
  },
  {
    id: "database-overviews",
    label: "数据库Overviews",
    anchors: ["数据库Overviews", "数据库 overviews", "Database Overviews"],
    fallbackRatio: 0.9,
  },
];

function parseArgs(argv) {
  const args = {
    raw: null,
    parsed: null,
    year: new Date().getFullYear(),
    milestones: [...DEFAULT_MILESTONES],
    dashboardUrl: DEFAULT_DASHBOARD_URL,
    targetText: DEFAULT_TARGET_TEXT,
    targetHref: DEFAULT_TARGET_HREF,
    outputDir: DEFAULT_OUTPUT_DIR,
    browserPort: 9222,
    browserUserDataDir: path.join(os.tmpdir(), "dingtalk-live-report-cookie-browser"),
    chromePath: null,
    waitAfterClickMs: 8000,
    waitBeforeScreenshotMs: 1000,
    waitForPanelsMs: 60000,
    screenshotAttempts: 3,
    requireDashboardData: true,
    screenshotSections: DEFAULT_SCREENSHOT_SECTIONS.map((section) => section.id),
    timeRangeMode: "live-window",
    clickTimeoutMs: 60000,
    directFallback: true,
    viewportWidth: 1440,
    viewportHeight: 1200,
    fullPage: true,
    collectPast: false,
    pastGraceMinutes: 0,
    dryRun: false,
    pretty: false,
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    switch (token) {
      case "--raw":
        args.raw = argv[++i];
        break;
      case "--parsed":
        args.parsed = argv[++i];
        break;
      case "--year":
        args.year = Number(argv[++i]);
        break;
      case "--milestones":
        args.milestones = parseMilestones(argv[++i]);
        break;
      case "--dashboard-url":
        args.dashboardUrl = argv[++i];
        break;
      case "--target-text":
        args.targetText = argv[++i];
        break;
      case "--target-href":
        args.targetHref = argv[++i];
        break;
      case "--output-dir":
        args.outputDir = path.resolve(argv[++i]);
        break;
      case "--browser-port":
      case "--port":
        args.browserPort = Number(argv[++i]);
        break;
      case "--browser-user-data-dir":
      case "--user-data-dir":
        args.browserUserDataDir = path.resolve(argv[++i]);
        break;
      case "--chrome-path":
        args.chromePath = argv[++i];
        break;
      case "--wait-after-click-ms":
        args.waitAfterClickMs = Number(argv[++i]);
        break;
      case "--wait-before-screenshot-ms":
        args.waitBeforeScreenshotMs = Number(argv[++i]);
        break;
      case "--wait-for-panels-ms":
        args.waitForPanelsMs = Number(argv[++i]);
        break;
      case "--screenshot-attempts":
        args.screenshotAttempts = Number(argv[++i]);
        break;
      case "--no-require-dashboard-data":
        args.requireDashboardData = false;
        break;
      case "--screenshot-sections":
        args.screenshotSections = parseScreenshotSections(argv[++i]);
        break;
      case "--single-screenshot":
        args.screenshotSections = ["overview"];
        break;
      case "--time-range-mode":
        args.timeRangeMode = argv[++i];
        break;
      case "--current-time-range":
        args.timeRangeMode = "current";
        break;
      case "--click-timeout-ms":
        args.clickTimeoutMs = Number(argv[++i]);
        break;
      case "--no-direct-fallback":
        args.directFallback = false;
        break;
      case "--viewport":
        {
          const [width, height] = String(argv[++i]).split(/[xX,*]/).map(Number);
          args.viewportWidth = width;
          args.viewportHeight = height;
        }
        break;
      case "--viewport-width":
        args.viewportWidth = Number(argv[++i]);
        break;
      case "--viewport-height":
        args.viewportHeight = Number(argv[++i]);
        break;
      case "--no-full-page":
        args.fullPage = false;
        break;
      case "--collect-past":
        args.collectPast = true;
        break;
      case "--past-grace-minutes":
        args.pastGraceMinutes = Number(argv[++i]);
        break;
      case "--dry-run":
        args.dryRun = true;
        break;
      case "--pretty":
        args.pretty = true;
        break;
      default:
        throw new Error(`unexpected argument: ${token}`);
    }
  }

  if (!args.raw && !args.parsed) {
    throw new Error("pass --raw <file> or --parsed <file>");
  }
  if (!args.milestones.length) {
    throw new Error("pass at least one milestone");
  }
  if (!Number.isFinite(args.viewportWidth) || !Number.isFinite(args.viewportHeight)) {
    throw new Error("invalid viewport");
  }
  if (!["live-window", "current"].includes(args.timeRangeMode)) {
    throw new Error("invalid --time-range-mode, expected live-window or current");
  }
  if (!Number.isFinite(args.waitForPanelsMs) || args.waitForPanelsMs <= 0) {
    throw new Error("invalid --wait-for-panels-ms");
  }
  if (!Number.isFinite(args.screenshotAttempts) || args.screenshotAttempts <= 0) {
    throw new Error("invalid --screenshot-attempts");
  }
  validateScreenshotSections(args.screenshotSections);
  return args;
}

function parseMilestones(value) {
  return String(value)
    .split(/[,\s，、]+/)
    .map((part) => Number(part.replace(/分钟/g, "")))
    .filter((minutes) => Number.isFinite(minutes) && minutes > 0);
}

function parseScreenshotSections(value) {
  return String(value)
    .split(/[,\s，、]+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function validateScreenshotSections(sections) {
  const allowed = new Set(DEFAULT_SCREENSHOT_SECTIONS.map((section) => section.id));
  for (const section of sections) {
    if (!allowed.has(section)) {
      throw new Error(
        `invalid screenshot section: ${section}; expected one of ${[...allowed].join(", ")}`,
      );
    }
  }
}

function selectedScreenshotSections(args) {
  const selected = new Set(args.screenshotSections);
  return DEFAULT_SCREENSHOT_SECTIONS.filter((section) => selected.has(section.id));
}

function readParsed(args) {
  if (args.parsed) {
    return JSON.parse(fs.readFileSync(args.parsed, "utf8"));
  }
  return parseText(fs.readFileSync(args.raw, "utf8"), args.year);
}

function parseLocalDateTime(date, time) {
  const match = String(date || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  const timeMatch = String(time || "").match(/^(\d{1,2}):(\d{2})$/);
  if (!match || !timeMatch) {
    return null;
  }
  const [, year, month, day] = match;
  const [, hour, minute] = timeMatch;
  return new Date(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
    0,
  );
}

function formatLocalDateTime(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return [
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`,
  ].join(" ");
}

function formatFileDateTime(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    "-",
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join("");
}

function buildJobs(parsed, milestones, now = new Date()) {
  const grouped = new Map();

  for (const item of parsed.items || []) {
    const liveDate = item.live_date || parsed.meta?.date;
    const startAt = parseLocalDateTime(liveDate, item.time);
    if (!startAt) {
      throw new Error(`cannot parse start time for live_id=${item.live_id || ""}`);
    }

    for (const milestone of milestones) {
      const runAt = new Date(startAt.getTime() + milestone * 60 * 1000);
      const key = `${liveDate}:${runAt.toISOString()}:${milestone}`;
      if (!grouped.has(key)) {
        grouped.set(key, {
          date: liveDate,
          milestone,
          start_at: startAt.toISOString(),
          start_at_local: formatLocalDateTime(startAt),
          run_at: runAt.toISOString(),
          run_at_local: formatLocalDateTime(runAt),
          wait_ms: runAt.getTime() - now.getTime(),
          lives: [],
        });
      }
      grouped.get(key).lives.push({
        live_id: item.live_id,
        title: item.title,
        start_at_local: formatLocalDateTime(startAt),
      });
    }
  }

  return [...grouped.values()].sort(
    (left, right) => new Date(left.run_at) - new Date(right.run_at),
  );
}

function dashboardUrlForJob(args, job) {
  if (args.timeRangeMode === "current") {
    return args.dashboardUrl;
  }
  const url = new URL(args.dashboardUrl);
  url.searchParams.set("from", String(new Date(job.start_at).getTime()));
  url.searchParams.set("to", String(new Date(job.run_at).getTime()));
  url.searchParams.delete("refresh");
  return url.toString();
}

async function openDashboard(args) {
  const launchedBrowser = launchBrowser({
    loginUrl: args.dashboardUrl,
    port: args.browserPort,
    userDataDir: args.browserUserDataDir,
    chromePath: args.chromePath,
    chromeApp: process.env.CHROME_APP || "Google Chrome",
  });
  let cdp = null;
  try {
    const wsUrl = await waitForPageWebSocket(args.browserPort, args.dashboardUrl, 60000);
    cdp = new CdpWebSocket(wsUrl);
    await cdp.connect();
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: args.viewportWidth,
      height: args.viewportHeight,
      deviceScaleFactor: 1,
      mobile: false,
    });
    await cdp.send("Page.navigate", { url: args.dashboardUrl });
    await waitForDocumentReady(cdp, 60000);
    if (shouldClickDashboardLink(args)) {
      await clickDashboardLink(cdp, args);
    }
    await sleep(args.waitAfterClickMs);
    return { cdp, launchedBrowser };
  } catch (error) {
    await closeBrowser(cdp, launchedBrowser, args.browserPort);
    throw error;
  }
}

function shouldClickDashboardLink(args) {
  const dashboard = new URL(args.dashboardUrl);
  const target = new URL(args.targetHref, args.dashboardUrl);
  return dashboard.origin !== target.origin || dashboard.pathname !== target.pathname;
}

async function waitForDocumentReady(cdp, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await cdp.send("Runtime.evaluate", {
      expression: "document.readyState",
      returnByValue: true,
    });
    if (result.result?.value === "complete" || result.result?.value === "interactive") {
      return;
    }
    await sleep(500);
  }
  throw new Error("timed out waiting for dashboard document ready");
}

async function clickDashboardLink(cdp, args) {
  const deadline = Date.now() + args.clickTimeoutMs;
  const hrefLiteral = JSON.stringify(args.targetHref);
  const textLiteral = JSON.stringify(args.targetText);

  while (Date.now() < deadline) {
    const result = await cdp.send("Runtime.evaluate", {
      awaitPromise: true,
      returnByValue: true,
      expression: `
        (() => {
          const expectedHref = ${hrefLiteral};
          const byHref = document.querySelector('a[href="${escapeForSelector(args.targetHref)}"]');
          const links = Array.from(document.querySelectorAll('a'));
          const byPartialHref = links.find((node) => {
            const href = node.href || node.getAttribute('href') || '';
            return href === expectedHref || href.includes('/d/SpSQKcpMl13/ying-xiao-zhi-bo-overviews');
          });
          const byText = links.find((node) => (node.textContent || '').trim() === ${textLiteral});
          const link = byHref || byPartialHref || byText;
          if (!link) {
            return { clicked: false, reason: 'link not found' };
          }
          link.scrollIntoView({ block: 'center', inline: 'center' });
          link.click();
          return {
            clicked: true,
            href: link.getAttribute('href'),
            text: (link.textContent || '').trim(),
            location: location.href,
            expectedHref
          };
        })()
      `,
    });
    if (result.result?.value?.clicked) {
      await waitForOverviewRoute(cdp, args, args.clickTimeoutMs);
      return result.result.value;
    }
    await sleep(1000);
  }
  if (!args.directFallback) {
    throw new Error(`timed out waiting for dashboard link: ${args.targetText}`);
  }

  const fallbackUrl = /^https?:\/\//i.test(args.targetHref)
    ? args.targetHref
    : `${new URL(args.dashboardUrl).origin}/#${args.targetHref}`;
  process.stderr.write(
    `dashboard link not found, navigating directly to ${fallbackUrl}\n`,
  );
  await cdp.send("Page.navigate", { url: fallbackUrl });
  await waitForDocumentReady(cdp, 60000);
  await waitForOverviewRoute(cdp, args, args.clickTimeoutMs);
  return {
    clicked: false,
    fallback: true,
    href: args.targetHref,
    text: args.targetText,
    location: fallbackUrl,
  };
}

function escapeForSelector(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

async function waitForOverviewRoute(cdp, args, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await cdp.send("Runtime.evaluate", {
      expression: "location.href",
      returnByValue: true,
    });
    const href = String(result.result?.value || "");
    const targetPath = (() => {
      try {
        return new URL(args.targetHref, args.dashboardUrl).pathname;
      } catch {
        return args.targetHref;
      }
    })();
    if (
      href.includes(args.targetHref) ||
      href.includes(encodeURI(args.targetHref)) ||
      href.includes(targetPath)
    ) {
      return href;
    }
    await sleep(500);
  }
  throw new Error(`timed out waiting for overview route: ${args.targetHref}`);
}

async function captureScreenshot(cdp, args, job) {
  const dashboardUrl = dashboardUrlForJob(args, job);
  let panelState = null;
  for (let attempt = 1; attempt <= args.screenshotAttempts; attempt += 1) {
    await cdp.send("Page.navigate", { url: dashboardUrl });
    await waitForDocumentReady(cdp, 60000);
    await waitForOverviewRoute(cdp, { ...args, targetHref: dashboardUrl }, args.clickTimeoutMs);
    try {
      panelState = await waitForDashboardPanels(cdp, args.waitForPanelsMs, {
        requireData: args.requireDashboardData,
      });
      break;
    } catch (error) {
      if (attempt >= args.screenshotAttempts) {
        throw error;
      }
      process.stderr.write(
        `dashboard data not ready for T+${job.milestone}, retrying ${attempt}/${args.screenshotAttempts}: ${error.message}\n`,
      );
      await sleep(2000);
    }
  }
  await sleep(args.waitBeforeScreenshotMs);
  await assertNotErrorPage(cdp);

  const dateDir = path.join(args.outputDir, job.date);
  fs.mkdirSync(dateDir, { recursive: true });
  const runAt = new Date(job.run_at);
  const capturedAt = new Date();
  const screenshots = [];

  for (const section of selectedScreenshotSections(args)) {
    await scrollToDashboardSection(cdp, section);
    await waitForViewportPanels(cdp, args.waitForPanelsMs, {
      requireData: args.requireDashboardData,
      section,
    });
    await sleep(args.waitBeforeScreenshotMs);
    const shot = await cdp.send("Page.captureScreenshot", {
      format: "png",
      fromSurface: true,
      captureBeyondViewport: false,
    });
    const filePath = path.join(
      dateDir,
      `monitor-${section.id}-T${job.milestone}-${formatFileDateTime(runAt)}-captured-${formatFileDateTime(capturedAt)}.png`,
    );
    fs.writeFileSync(filePath, Buffer.from(shot.data, "base64"));
    screenshots.push({
      section: section.id,
      label: section.label,
      filePath,
    });
  }
  return { filePath: screenshots[0]?.filePath || null, screenshots, dashboardUrl, panelState };
}

async function scrollToDashboardSection(cdp, section) {
  const result = await cdp.send("Runtime.evaluate", {
    awaitPromise: true,
    returnByValue: true,
    expression: `
      (async () => {
        const scrollingElement = document.scrollingElement || document.documentElement;
        const fixedOffset = 90;
        const candidates = Array.from(document.querySelectorAll(
          'main,[role="main"],[class*="scroll"],[class*="Scroll"],[class*="dashboard"],[class*="Dashboard"],[data-testid*="scroll"],[data-testid*="dashboard"]'
        ));
        const scrollContainers = [scrollingElement, ...candidates]
          .filter((node, index, nodes) => node && nodes.indexOf(node) === index)
          .filter((node) => node.scrollHeight > node.clientHeight + 80 && node.clientHeight > 250)
          .sort((left, right) =>
            (right.scrollHeight - right.clientHeight) - (left.scrollHeight - left.clientHeight),
          )
          .slice(0, 6);
        const scrollTo = (container, top) => {
          if (container === scrollingElement || container === document.body || container === document.documentElement) {
            scrollingElement.scrollTo({ top, left: 0, behavior: 'instant' });
          } else {
            container.scrollTo({ top, left: 0, behavior: 'instant' });
          }
        };
        if (${JSON.stringify(section.id)} === 'overview') {
          scrollContainers.forEach((container) => scrollTo(container, 0));
          await new Promise((resolve) => setTimeout(resolve, 300));
          return { found: true, section: ${JSON.stringify(section.id)}, top: 0 };
        }

        const anchors = ${JSON.stringify(section.anchors || [])};
        const normalizedAnchors = anchors.map((anchor) => String(anchor).replace(/\\s+/g, '').toLowerCase());
        const findMatch = () => {
          const nodes = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[data-testid],.section-heading,.dashboard-row,.panel-title-container,div,span'));
          return nodes.find((node) => {
            const text = (node.innerText || node.textContent || '').replace(/\\s+/g, '').trim();
            if (!text || text.length > 160) {
              return false;
            }
            const lower = text.toLowerCase();
            return normalizedAnchors.some((anchor) => lower.includes(anchor));
          });
        };

        let match = null;
        let matchedContainer = null;
        for (const container of scrollContainers) {
          const viewportHeight = container === scrollingElement
            ? window.innerHeight
            : container.clientHeight;
          const maxScroll = Math.max(container.scrollHeight - viewportHeight, 0);
          const step = Math.max(Math.floor(viewportHeight * 0.8), 600);
          let scanned = 0;
          for (let top = 0; top <= maxScroll + step && scanned < 18; top += step, scanned += 1) {
            scrollTo(container, Math.min(top, maxScroll));
            await new Promise((resolve) => setTimeout(resolve, 300));
            match = findMatch();
            if (match) {
              matchedContainer = container;
              break;
            }
          }
          if (match) {
            break;
          }
        }
        if (!match) {
          const fallbackRatio = ${JSON.stringify(section.fallbackRatio || null)};
          if (fallbackRatio !== null && scrollContainers.length) {
            const container = scrollContainers[0];
            const maxScroll = Math.max(container.scrollHeight - (container === scrollingElement ? window.innerHeight : container.clientHeight), 0);
            const top = Math.floor(maxScroll * fallbackRatio);
            scrollTo(container, top);
            await new Promise((resolve) => setTimeout(resolve, 700));
            return {
              found: true,
              fallback: true,
              section: ${JSON.stringify(section.id)},
              top,
              scrollHeight: container.scrollHeight,
              clientHeight: container.clientHeight
            };
          }
          return {
            found: false,
            section: ${JSON.stringify(section.id)},
            anchors,
            containers: scrollContainers.map((node) => ({ scrollHeight: node.scrollHeight, clientHeight: node.clientHeight, className: node.className || '', id: node.id || '' })),
            excerpt: (document.body && document.body.innerText || '').slice(0, 500)
          };
        }
        const rect = match.getBoundingClientRect();
        const container = matchedContainer || scrollingElement;
        const containerRect = container === scrollingElement
          ? { top: 0 }
          : container.getBoundingClientRect();
        const currentTop = container === scrollingElement ? scrollingElement.scrollTop : container.scrollTop;
        const top = Math.max(0, rect.top - containerRect.top + currentTop - fixedOffset);
        scrollTo(container, top);
        return {
          found: true,
          section: ${JSON.stringify(section.id)},
          top,
          text: (match.innerText || match.textContent || '').trim().slice(0, 120)
        };
      })()
    `,
  });
  const value = result.result?.value || {};
  if (!value.found) {
    throw new Error(
      `cannot find monitor dashboard section ${section.id}: ${(value.excerpt || "").slice(0, 200)}`,
    );
  }
  await sleep(1000);
}

async function waitForDashboardPanels(cdp, timeoutMs, options = {}) {
  const requireData = options.requireData !== false;
  const deadline = Date.now() + timeoutMs;
  let lastValue = null;
  while (Date.now() < deadline) {
    await assertNotErrorPage(cdp);
    const result = await cdp.send("Runtime.evaluate", {
      awaitPromise: true,
      returnByValue: true,
      expression: `
        (() => {
          const text = (document.body && document.body.innerText || '').trim();
          const loadingText = /loading|querying|加载中|正在加载|请求中/i.test(text);
          const spinners = document.querySelectorAll('[aria-label*="Loading"], [class*="spinner"], [class*="Spinner"]').length;
          const panels = document.querySelectorAll('[data-panelid], .panel-container, .react-grid-item').length;
          const canvases = document.querySelectorAll('canvas').length;
          const svgs = document.querySelectorAll('svg').length;
          const grafanaChrome = /grafana|overviews/i.test(document.title || text);
          const panelNodes = Array.from(document.querySelectorAll('[data-panelid], .panel-container, .react-grid-item'));
          const panelText = panelNodes
            .map((node) => (node.innerText || node.textContent || '').trim())
            .filter(Boolean)
            .join(' ')
            .replace(/\\s+/g, ' ');
          const tableCells = panelNodes.flatMap((node) =>
            Array.from(node.querySelectorAll('td, th, [role="cell"], [role="columnheader"]')),
          )
            .map((node) => (node.textContent || '').trim())
            .filter(Boolean);
          const metricValue = /\\d+(?:\\.\\d+)?\\s*(?:req\\/s|GiB|MiB|KiB)\\b/i;
          const tableDataCells = tableCells.filter((cell) => metricValue.test(cell)).length;
          const hasData =
            metricValue.test(panelText) ||
            tableDataCells >= 3 ||
            /\\b(?:codecamp-marketing-web-api|lbk-web-customer)\\b[\\s\\S]{0,120}\\d+(?:\\.\\d+)?\\s*(?:req\\/s|GiB|MiB|KiB)\\b/i.test(panelText);
          const baseReady = grafanaChrome && panels > 0 && !loadingText && spinners === 0;
          return {
            ready: baseReady && (${requireData ? "hasData" : "true"}),
            baseReady,
            hasData,
            title: document.title || '',
            location: location.href,
            panels,
            canvases,
            svgs,
            loadingText,
            spinners,
            tableCells: tableCells.length,
            tableDataCells,
            excerpt: text.slice(0, 200)
          };
        })()
      `,
    });
    lastValue = result.result?.value || null;
    if (lastValue?.ready) {
      return lastValue;
    }
    await sleep(1000);
  }
  throw new Error(
    `timed out waiting for Grafana panels: ${JSON.stringify(lastValue || {})}`,
  );
}

async function waitForViewportPanels(cdp, timeoutMs, options = {}) {
  const requireData = options.requireData !== false;
  const section = options.section || { id: "unknown" };
  const deadline = Date.now() + timeoutMs;
  let lastValue = null;
  while (Date.now() < deadline) {
    await assertNotErrorPage(cdp);
    const result = await cdp.send("Runtime.evaluate", {
      awaitPromise: true,
      returnByValue: true,
      expression: `
        (() => {
          const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
          const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
          const loadingText = /loading|querying|加载中|正在加载|请求中/i.test(document.body && document.body.innerText || '');
          const spinners = document.querySelectorAll('[aria-label*="Loading"], [class*="spinner"], [class*="Spinner"]').length;
          const panelNodes = Array.from(document.querySelectorAll('[data-panelid], .panel-container, .react-grid-item'));
          const visiblePanelNodes = panelNodes.filter((node) => {
            const rect = node.getBoundingClientRect();
            return rect.bottom > 100 && rect.top < viewportHeight - 20 && rect.right > 80 && rect.left < viewportWidth;
          });
          const visibleText = visiblePanelNodes
            .map((node) => (node.innerText || node.textContent || '').trim())
            .filter(Boolean)
            .join(' ')
            .replace(/\\s+/g, ' ');
          const tableCells = visiblePanelNodes.flatMap((node) =>
            Array.from(node.querySelectorAll('td, th, [role="cell"], [role="columnheader"]')),
          )
            .map((node) => (node.textContent || '').trim())
            .filter(Boolean);
          const metricValue = /\\d+(?:\\.\\d+)?\\s*(?:req\\/s|GiB|MiB|KiB|MB|KB|ms|s)\\b/i;
          const namedMetricValue = /\\b(?:min|max|avg|current|WSS|RSS|CPU|QPS|TPS|连接|耗时|延迟)\\b[\\s\\S]{0,120}\\d+(?:\\.\\d+)?/i;
          const tableDataCells = tableCells.filter((cell) => metricValue.test(cell)).length;
          const hasData =
            metricValue.test(visibleText) ||
            namedMetricValue.test(visibleText) ||
            tableDataCells >= 3;
          const ready = visiblePanelNodes.length > 0 && !loadingText && spinners === 0 && (${requireData ? "hasData" : "true"});
          return {
            ready,
            hasData,
            visiblePanels: visiblePanelNodes.length,
            loadingText,
            spinners,
            tableCells: tableCells.length,
            tableDataCells,
            scrollY: window.scrollY,
            excerpt: visibleText.slice(0, 240)
          };
        })()
      `,
    });
    lastValue = result.result?.value || null;
    if (lastValue?.ready) {
      return lastValue;
    }
    await sleep(1000);
  }
  throw new Error(
    `timed out waiting for Grafana viewport section ${section.id}: ${JSON.stringify(lastValue || {})}`,
  );
}

async function assertNotErrorPage(cdp) {
  const result = await cdp.send("Runtime.evaluate", {
    returnByValue: true,
    expression: `
      (() => {
        const text = (document.body && document.body.innerText || '').trim();
        return {
          title: document.title || '',
          location: location.href,
          isError:
            /(^|\\s)(404|403)(\\s|$)/.test(text) ||
            /(^|\\s)(404|403)(\\s|$)/.test(document.title || '') ||
            /not found|forbidden|can not enter this page|page not found/i.test(text) ||
            /not found|forbidden|page not found/i.test(document.title || ''),
          excerpt: text.slice(0, 200)
        };
      })()
    `,
  });
  const value = result.result?.value || {};
  if (value.isError) {
    throw new Error(`monitor dashboard error page at ${value.location}: ${value.excerpt}`);
  }
}

async function runScheduler(args, parsed) {
  const jobs = buildJobs(parsed, args.milestones);
  const results = [];
  let cdp = null;
  let launchedBrowser = null;

  try {
    for (const job of jobs) {
      const waitMs = new Date(job.run_at).getTime() - Date.now();
      const pastMs = Math.abs(Math.min(waitMs, 0));
      if (waitMs < 0 && !args.collectPast) {
        results.push({ ...job, status: "skipped-past" });
        continue;
      }
      if (
        waitMs < 0 &&
        args.pastGraceMinutes > 0 &&
        pastMs > args.pastGraceMinutes * 60 * 1000
      ) {
        results.push({ ...job, status: "skipped-past-grace" });
        continue;
      }

      if (waitMs > 0) {
        process.stderr.write(
          `waiting ${Math.ceil(waitMs / 1000)}s for monitor screenshot T+${job.milestone}\n`,
        );
        await sleep(waitMs);
      }

      if (!cdp) {
        const dashboard = await openDashboard(args);
        cdp = dashboard.cdp;
        launchedBrowser = dashboard.launchedBrowser;
      }

      try {
        const captured = await captureScreenshot(cdp, args, job);
        results.push({
          ...job,
          dashboard_url: captured.dashboardUrl,
          screenshot: captured.filePath,
          screenshots: captured.screenshots,
          captured_at: new Date().toISOString(),
          status: "captured",
        });
        for (const screenshot of captured.screenshots || []) {
          process.stderr.write(`captured monitor screenshot: ${screenshot.filePath}\n`);
        }
      } catch (error) {
        results.push({ ...job, status: "failed", error: error.message });
        process.stderr.write(`failed monitor screenshot T+${job.milestone}: ${error.message}\n`);
      }
    }
  } finally {
    if (cdp) {
      await closeBrowser(cdp, launchedBrowser, args.browserPort);
    }
  }

  return {
    date: parsed.meta?.date || jobs[0]?.date || null,
    output_dir: args.outputDir,
    dashboard_url: args.dashboardUrl,
    target_href: args.targetHref,
    results,
  };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const parsed = readParsed(args);
  if (parsed.errors?.length) {
    throw new Error(parsed.errors.join("; "));
  }

  const jobs = buildJobs(parsed, args.milestones);
  if (args.dryRun) {
    process.stdout.write(
      `${JSON.stringify(
        {
          now: new Date().toISOString(),
          output_dir: args.outputDir,
          dashboard_url: args.dashboardUrl,
          target_href: args.targetHref,
          time_range_mode: args.timeRangeMode,
          screenshot_sections: args.screenshotSections,
          jobs: jobs.map((job) => ({
            ...job,
            dashboard_url: dashboardUrlForJob(args, job),
          })),
        },
        null,
        args.pretty ? 2 : 0,
      )}\n`,
    );
    return;
  }

  const payload = await runScheduler(args, parsed);
  process.stdout.write(`${JSON.stringify(payload, null, args.pretty ? 2 : 0)}\n`);
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exit(1);
  });
}

module.exports = {
  buildJobs,
  dashboardUrlForJob,
  parseMilestones,
};
