/** Production-build, actual HTTP qualification. Output contains only synthetic metrics. */
import { spawn, execFileSync } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir, cpus, platform, release, totalmem } from "node:os";
import path from "node:path";
import { chromium } from "@playwright/test";
import { preview } from "vite";
import { fileURLToPath } from "node:url";
process.chdir(path.dirname(fileURLToPath(import.meta.url)));

const root = await mkdtemp(path.join(tmpdir(), "provider-ui-qualification-"));
const output = process.argv[2];
if (!output) throw new Error("Pass an output JSON path");
const api = spawn(
  "python3",
  [
    "-u",
    "scripts/qualification/serve.py",
    "--root",
    path.join(root, "storage"),
  ],
  {
    cwd: path.resolve(".."),
    env: { ...process.env, PYTHONPATH: "src" },
    stdio: ["ignore", "pipe", "pipe"],
  },
);
let browser, frontend;
let errors = "";
api.stderr.on("data", (d) => {
  errors = (errors + d).slice(-4000);
});
try {
  const base = await new Promise((resolve, reject) => {
    let text = "";
    const timer = setTimeout(
      () => reject(new Error(`API setup timeout: ${errors}`)),
      120000,
    );
    api.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`API exited ${code}: ${errors}`));
    });
    api.stdout.on("data", (data) => {
      text += data;
      const m = text.match(/QUALIFICATION_API=(http:\/\/127\.0\.0\.1:\d+)/);
      if (m) {
        clearTimeout(timer);
        resolve(m[1]);
      }
    });
  });
  frontend = await preview({
    preview: {
      host: "127.0.0.1",
      port: 0,
      strictPort: true,
      proxy: { "/api": base },
    },
  });
  const address = frontend.httpServer.address();
  const url = `http://127.0.0.1:${address.port}`;
  const fixtures = (await (await fetch(`${base}/__qualification`)).json())
    .fixtures;
  browser = await chromium.launch();
  const report = {
    format_version: 1,
    fixture_sizes: [100, 1000],
    build: "production",
    browser: browser.version(),
    environment: {
      os: platform(),
      release: release(),
      cpu: cpus()[0].model,
      logical_cpus: cpus().length,
      memory_gib: Math.round(totalmem() / 2 ** 30),
    },
    method:
      "Five fresh-browser-context cold loads per population; trusted pointerdown to second animation frame for 30 row selections and 30 tab changes; loopback API. Lab proxy, not field INP. Setup excluded. Browser rendering and full HTTP path use synthetic approved feeds. No 10,000-record run.",
    results: [],
  };
  const percentile = (a, p) =>
    [...a].sort((x, y) => x - y)[Math.ceil(a.length * p) - 1];
  for (const fixture of fixtures) {
    const loads = [];
    let page, context;
    for (let trial = 0; trial < 5; trial++) {
      context = await browser.newContext({
        viewport: { width: 1440, height: 960 },
      });
      await context.addInitScript(() => {
        window.__longTasks = [];
        new PerformanceObserver((list) =>
          window.__longTasks.push(...list.getEntries().map((e) => e.duration)),
        ).observe({ type: "longtask", buffered: true });
      });
      page = await context.newPage();
      page.setDefaultTimeout(15000);
      const start = performance.now();
      await page.goto(
        `${url}/?view=feeds&feed=${fixture.feed_id}&version=${fixture.version_id}`,
      );
      await page
        .getByRole("heading", {
          name: "Dataset review · approved",
          exact: true,
        })
        .waitFor();
      await page
        .getByRole("button", { name: "Preview approved workbook", exact: true })
        .waitFor();
      loads.push(performance.now() - start);
      if (trial < 4) await context.close();
    }
    const endpoints = [];
    for (const endpoint of ["review-export", "review-preview?limit=5"]) {
      const timings = [];
      let bytes, data, server;
      for (let i = 0; i < 5; i++) {
        const start = performance.now();
        const response = await fetch(
          `${url}/api/feed-versions/${fixture.version_id}/${endpoint}`,
        );
        if (!response.ok) throw new Error(await response.text());
        const body = await response.text();
        timings.push(performance.now() - start);
        bytes = Buffer.byteLength(body);
        data = JSON.parse(body);
        server = response.headers.get("server-timing");
      }
      if (data.counts.directory !== fixture.count)
        throw new Error("Population mismatch");
      endpoints.push({
        endpoint,
        response_bytes: bytes,
        median_ms: percentile(timings, 0.5),
        max_ms: Math.max(...timings),
        last_server_timing: server,
        returned_directory: data.directory.length,
        total_directory: data.counts.directory,
        snapshot_id: data.snapshot_id,
      });
    }
    if (endpoints[0].snapshot_id !== endpoints[1].snapshot_id)
      throw new Error("Preview token diverges from full export");
    await page.evaluate(() => {
      window.__paint = [];
      document.addEventListener(
        "pointerdown",
        () => {
          const start = performance.now();
          requestAnimationFrame(() =>
            requestAnimationFrame(() =>
              window.__paint.push(performance.now() - start),
            ),
          );
        },
        true,
      );
    });
    const rows = page
      .getByRole("table", { name: "Delivery comparison entries" })
      .getByRole("button");
    const count = await rows.count();
    if (count < 2) throw new Error("Need selectable comparison evidence");
    for (let i = 0; i < 30; i++) {
      const before = await page.evaluate(() => window.__paint.length);
      await rows.nth(i % count).click();
      await page.waitForFunction((n) => window.__paint.length > n, before);
    }
    const paints = await page.evaluate(() => window.__paint);
    for (let i = 0; i < 30; i++) {
      const before = await page.evaluate(() => window.__paint.length);
      await page
        .getByRole("tab", {
          name: i % 2 === 0 ? "Original & history" : "Evidence & holds",
          exact: true,
        })
        .click();
      await page.waitForFunction((n) => window.__paint.length > n, before);
    }
    const tabPaints = (await page.evaluate(() => window.__paint)).slice(
      paints.length,
    );
    const longTasks = await page.evaluate(() => window.__longTasks);
    await page
      .getByRole("button", { name: "Preview approved workbook", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Download reviewed workbook XLSX",
        exact: true,
      })
      .waitFor();
    const sampleRows = await page
      .getByRole("region", { name: "Unresolved export issues", exact: true })
      .getByRole("row")
      .count();
    const session = await context.newCDPSession(page);
    await session.send("Performance.enable");
    async function retainedHeap() {
      await session.send("HeapProfiler.collectGarbage");
      return (await session.send("Performance.getMetrics")).metrics.find(
        (m) => m.name === "JSHeapUsedSize",
      ).value;
    }
    const beforeHeap = await retainedHeap();
    for (let i = 0; i < 10; i++) {
      await page
        .getByRole("navigation", { name: "Workbench navigation", exact: true })
        .getByRole("link", { name: "Work queue", exact: true })
        .click();
      await page
        .getByRole("heading", { name: "Provider work queue", exact: true })
        .waitFor();
      await page
        .getByRole("navigation", { name: "Workbench navigation", exact: true })
        .getByRole("link", { name: "Deliveries", exact: true })
        .click();
      await page
        .getByRole("button", {
          name: `Synthetic ${fixture.count}-record roster`,
          exact: false,
        })
        .click();
      await page
        .locator(`button[data-version-id="${fixture.version_id}"]`)
        .click();
      await page
        .getByRole("heading", {
          name: "Dataset review · approved",
          exact: true,
        })
        .waitFor();
    }
    const afterHeap = await retainedHeap();
    await page
      .getByRole("navigation", { name: "Workbench navigation", exact: true })
      .getByRole("link", { name: "Work queue", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "Search work", exact: true })
      .waitFor();
    await page.evaluate(() => {
      window.__keys = [];
      document.addEventListener(
        "keydown",
        () => {
          const t = performance.now();
          requestAnimationFrame(() =>
            requestAnimationFrame(() =>
              window.__keys.push(performance.now() - t),
            ),
          );
        },
        true,
      );
    });
    const search = page.getByRole("textbox", {
      name: "Search work",
      exact: true,
    });
    await search.pressSequentially(
      "Synthetic Provider 0001 Nashville Tennessee",
      { delay: 50 },
    );
    await page.waitForTimeout(100);
    const keyPaints = await page.evaluate(() => window.__keys);
    await page.goto(
      `${url}/?view=feeds&feed=${fixture.feed_id}&version=${fixture.version_id}`,
    );
    await page
      .getByRole("heading", { name: "Dataset review · approved", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Preview approved workbook", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Download reviewed workbook XLSX",
        exact: true,
      })
      .waitFor();
    const workbookStart = performance.now();
    const workbookResponse = await fetch(
      `${url}/api/feed-versions/${fixture.version_id}/review-export?format=xlsx&expected_snapshot=${endpoints[1].snapshot_id}`,
    );
    if (!workbookResponse.ok) throw new Error(await workbookResponse.text());
    const workbookBytes = Buffer.from(await workbookResponse.arrayBuffer());
    const workbookMs = performance.now() - workbookStart;
    const workbookPath = path.join(root, `directory-${fixture.count}.xlsx`);
    await writeFile(workbookPath, workbookBytes);
    execFileSync("python3", [
      "-c",
      "import sys;from openpyxl import load_workbook;b=load_workbook(sys.argv[1],read_only=True);s=b['Directory'];assert s.max_row==int(sys.argv[2])+1;rows=s.iter_rows(values_only=True);h=next(rows);z=h.index('zip');assert all(r[z]=='03701' for r in rows);b.close()",
      workbookPath,
      String(fixture.count),
    ]);
    await page.screenshot({
      path: path.join(root, `delivery-${fixture.count}-desktop.png`),
    });
    const widths = [];
    for (const width of [1280, 1024, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.waitForTimeout(100);
      widths.push({
        width,
        page_overflow: await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
      });
    }
    const desktopPage = page;
    const mobileContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      hasTouch: true,
      isMobile: true,
    });
    page = await mobileContext.newPage();
    page.setDefaultTimeout(15000);
    await page.goto(
      `${url}/?view=feeds&feed=${fixture.feed_id}&version=${fixture.version_id}`,
    );
    await page
      .getByRole("heading", { name: "Dataset review · approved", exact: true })
      .waitFor();
    await page
      .getByRole("button", { name: "Preview approved workbook", exact: true })
      .click();
    await page
      .getByRole("button", {
        name: "Download reviewed workbook XLSX",
        exact: true,
      })
      .waitFor();
    const touchTarget = await page
      .getByRole("button", {
        name: "Download reviewed workbook XLSX",
        exact: true,
      })
      .boundingBox();
    if (touchTarget.height < 44)
      throw new Error("Primary touch target is too small");
    await page.emulateMedia({ reducedMotion: "reduce" });
    const returnButton = page.getByRole("button", {
      name: "← Back to deliveries",
      exact: true,
    });
    await returnButton.click();
    const versionButton = page.locator(
      `button[data-version-id="${fixture.version_id}"]`,
    );
    await versionButton.focus();
    await page.keyboard.press("Enter");
    const detail = page.getByRole("region", {
      name: "Dataset review · approved",
      exact: true,
    });
    await page.waitForFunction(() =>
      document.activeElement?.classList.contains("mf-version-detail"),
    );
    const downloadEvent = page.waitForEvent("download");
    await page
      .getByRole("button", {
        name: "Download reviewed workbook XLSX",
        exact: true,
      })
      .click();
    const browserDownload = await downloadEvent;
    if (await browserDownload.failure())
      throw new Error("Narrow workbook download failed");
    const browserWorkbook = path.join(
      root,
      `browser-directory-${fixture.count}.xlsx`,
    );
    await browserDownload.saveAs(browserWorkbook);
    execFileSync("python3", [
      "-c",
      "import sys;from openpyxl import load_workbook;b=load_workbook(sys.argv[1],read_only=True);assert b['Directory'].max_row==int(sys.argv[2])+1;b.close()",
      browserWorkbook,
      String(fixture.count),
    ]);
    const issueScroller = page.getByRole("region", {
      name: "Unresolved export issues",
      exact: true,
    });
    await issueScroller.focus();
    await page.keyboard.press("ArrowRight");
    await page.waitForFunction(
      () =>
        document.querySelector('[aria-label="Unresolved export issues"]')
          .scrollLeft > 0,
    );
    await issueScroller.evaluate((element) => {
      element.scrollLeft = 0;
    });
    await page
      .getByRole("region", { name: "Approved export review", exact: true })
      .screenshot({
        path: path.join(root, `export-${fixture.count}-narrow.png`),
      });
    await page.screenshot({
      path: path.join(root, `delivery-${fixture.count}-narrow.png`),
    });
    await mobileContext.close();
    page = desktopPage;
    const stressContext = await browser.newContext({
      viewport: { width: 1440, height: 960 },
    });
    const stressPage = await stressContext.newPage();
    const stressSession = await stressContext.newCDPSession(stressPage);
    await stressSession.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await stressSession.send("Network.enable");
    await stressSession.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 150,
      downloadThroughput: 5 * 1024 * 1024,
      uploadThroughput: 5 * 1024 * 1024,
    });
    const stressStart = performance.now();
    await stressPage.goto(
      `${url}/?view=feeds&feed=${fixture.feed_id}&version=${fixture.version_id}`,
    );
    await stressPage
      .getByRole("heading", { name: "Dataset review · approved", exact: true })
      .waitFor();
    const stressLoad = performance.now() - stressStart;
    await stressContext.close();
    report.results.push({
      records: fixture.count,
      usability: {
        narrow_keyboard_list_detail_focus: true,
        narrow_table_keyboard_scroll: true,
        primary_touch_target_height_px: touchTarget.height,
        actual_touch_context: true,
        narrow_browser_download_rows: fixture.count,
        reduced_motion_flow: true,
      },
      workbook: {
        milliseconds: workbookMs,
        bytes: workbookBytes.length,
        independently_inspected_rows: fixture.count,
        leading_zero_zip_preserved: true,
      },
      tab_next_paint_proxy_ms: {
        samples: tabPaints.length,
        p95: percentile(tabPaints, 0.95),
        max: Math.max(...tabPaints),
      },
      long_tasks_ms: {
        count: longTasks.length,
        max: Math.max(0, ...longTasks),
        scope: "Fifth cold load, 30 selection and 30 tab interactions",
      },
      filter_typing_next_paint_proxy_ms: {
        samples: keyPaints.length,
        p95: percentile(keyPaints, 0.95),
        max: Math.max(...keyPaints),
        scope:
          "Shared work queue; both fixtures present, the API returns all work and the UI renders at most 200 matches after filtering. Local filter typing over the pooled queue, not population-isolated work throughput.",
      },
      retained_heap_bytes: {
        before: beforeHeap,
        after_20_workspace_switches: afterHeap,
        delta: afterHeap - beforeHeap,
        note: "Forced GC at both endpoints, one lab sample; existing query caches may retain data. This does not establish absence of leaks.",
      },
      stress: {
        cpu_slowdown: 4,
        added_latency_ms: 150,
        bandwidth_mib_s: 5,
        cold_load_ms: stressLoad,
        trials: 1,
      },
      cold_load_ms: {
        trials: loads,
        median: percentile(loads, 0.5),
        min: Math.min(...loads),
        max: Math.max(...loads),
      },
      row_selection_next_paint_proxy_ms: {
        samples: paints.length,
        p95: percentile(paints, 0.95),
        max: Math.max(...paints),
      },
      endpoints,
      rendered_unresolved_rows_including_header: sampleRows,
      widths,
      budgets: {
        cold_load_3s: Math.max(...loads) <= 3000,
        interaction_p95_200ms:
          Math.max(
            percentile(paints, 0.95),
            percentile(tabPaints, 0.95),
            percentile(keyPaints, 0.95),
          ) <= 200,
        no_page_overflow: widths.every((item) => !item.page_overflow),
      },
    });
    await context.close();
  }
  report.capture_directory = root;
  await writeFile(output, JSON.stringify(report, null, 2) + "\n");
  if (
    report.results.some((result) =>
      Object.values(result.budgets).some((passed) => !passed),
    )
  )
    process.exitCode = 1;
  console.log(
    JSON.stringify({
      output,
      captures: root,
      results: report.results.map((r) => ({
        records: r.records,
        load_median_ms: r.cold_load_ms.median,
        interaction_p95_ms: r.row_selection_next_paint_proxy_ms.p95,
        preview_bytes: r.endpoints[1].response_bytes,
        budgets: r.budgets,
      })),
    }),
  );
} finally {
  if (browser) await browser.close();
  if (frontend)
    await new Promise((resolve) => frontend.httpServer.close(resolve));
  api.kill("SIGTERM");
}
