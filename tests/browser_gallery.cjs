// Real Chromium DOM test with a minimal ComfyUI app stub; no model requests.
// node tests/browser_gallery.cjs <playwright-core path> <chrome.exe path> <output directory>
const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require(process.argv[2] || "playwright-core");
const root = path.resolve(__dirname, "..", "web");
const output = path.resolve(process.argv[4] || path.join(__dirname, "browser-output"));
fs.mkdirSync(output, { recursive: true });
const appScript = `export const app = { registerExtension(ext) { window.extension = ext; } };`;
const html = `<!doctype html><meta charset="utf-8"><style>body{background:#12141a;color:#ddd;font-family:system-ui;padding:24px}button{padding:10px}</style>
<h1>RunningHub Gallery — local UI harness</h1><p>Mock ComfyUI host. No generation or billing.</p><button id="open">打开画廊</button>
<script type="module">
import './extensions/SynVow-PresetGallery-RunningHub/gallery.js';
function Node() { this.widgets = [{name:'preset',value:'街头大楼 3D 立体广告看板',callback(value){window.selected=value}}]; }
Node.prototype.addWidget = function(type,label,value,callback,options){this.open=callback;window.widgetOptions=options};
Node.prototype.setDirtyCanvas = function(){window.dirty=true};
await window.extension.beforeRegisterNodeDef(Node,{name:'SynVowRHPresetGallery'});
window.testNode=new Node();window.testNode.onNodeCreated();
document.querySelector('#open').onclick=()=>window.testNode.open();window.ready=true;
</script>`;
let failList = false;
let failThumb = false;
const requests = [];
const server = http.createServer((req, res) => {
  requests.push(req.url);
  let url = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
  if (url.startsWith("/proxy/instance/")) url = url.slice("/proxy/instance".length);
  if (url === "/") { res.setHeader("Content-Type", "text/html; charset=utf-8"); res.end(html); return; }
  if (url === "/scripts/app.js") { res.setHeader("Content-Type", "text/javascript"); res.end(appScript); return; }
  const prefix = "/extensions/SynVow-PresetGallery-RunningHub/";
  if (!url.startsWith(prefix)) { res.writeHead(404).end(); return; }
  const file = path.resolve(root, url.slice(prefix.length));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  if (failList && file.endsWith("commands.json")) { res.writeHead(503).end(); return; }
  if (failThumb && file.endsWith(".jpg")) { res.writeHead(404).end(); return; }
  if (!fs.existsSync(file)) { res.writeHead(404).end(); return; }
  res.setHeader("Content-Type", file.endsWith(".js") ? "text/javascript" : file.endsWith(".json") ? "application/json" : "image/jpeg");
  fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({ executablePath: process.argv[3], headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const base = `http://127.0.0.1:${server.address().port}`;
  const waitCards = () => page.waitForFunction(() => document.querySelectorAll('.synrhg-card').length === 200);
  const visibleCards = () => page.locator(".synrhg-card:visible").count();
  const report = [];
  try {
    for (const prefix of ["/", "/proxy/instance/"]) {
      await page.goto(base + prefix);
      await page.waitForFunction(() => window.ready);
      await page.click("#open");
      await waitCards();
      assert.equal(await visibleCards(), 200);
      await page.evaluate(() => window.testNode.open());
      assert.equal(await page.locator(".synrhg-dialog").count(), 1);
      assert.equal(await page.locator(".synrhg-tabs button").count(), 5);
      await page.getByRole("button", { name: "产品广告", exact: true }).click();
      assert.equal(await visibleCards(), 54);
      await page.getByRole("button", { name: "全部", exact: true }).click();
      await page.locator(".synrhg-search").fill("/3dbillboard");
      assert.equal(await visibleCards(), 1);
      await page.locator(".synrhg-search").fill("街頭大樓");
      assert.equal(await visibleCards(), 1);
      await page.locator(".synrhg-search").fill("no-match-xyz-999");
      assert.equal(await visibleCards(), 0);
      assert.equal(await page.locator(".synrhg-empty:visible").count(), 1);
      await page.locator(".synrhg-search").fill("/subwayad");
      await page.locator(".synrhg-card:visible").click();
      await page.waitForSelector(".synrhg-dialog", { state: "detached" });
      assert.equal(await page.evaluate(() => window.testNode.widgets[0].value), "地铁站台广告");
      assert.equal(await page.evaluate(() => window.selected), "地铁站台广告");
      assert.equal(await page.evaluate(() => window.dirty), true);
      assert.equal(await page.evaluate(() => window.widgetOptions.serialize), false);
      report.push(`PASS: ${prefix} assets, 200 cards, category, EN/traditional search, empty state, selection, callback, singleton`);
    }
    await page.click("#open");
    await waitCards();
    const resourceStatus = await page.locator(".synrhg-card img").evaluateAll(async images => {
      const results = await Promise.all(images.map(async image => (await fetch(image.src)).status));
      return { total: results.length, failed: results.filter(status => status !== 200).length };
    });
    assert.deepEqual(resourceStatus, { total: 200, failed: 0 });
    await page.waitForFunction(() => [...document.querySelectorAll('.synrhg-card img')].slice(0, 6).every(image => image.complete && image.naturalWidth > 0));
    await page.screenshot({ path: path.join(output, "gallery-desktop.png") });
    await page.keyboard.press("Escape");
    await page.waitForSelector(".synrhg-dialog", { state: "detached" });
    report.push("PASS: all 200 thumbnail URLs return 200; desktop render and Escape close");

    await page.setViewportSize({ width: 390, height: 844 });
    await page.click("#open");
    await waitCards();
    const bounds = await page.locator(".synrhg-dialog").boundingBox();
    assert(bounds.x >= 0 && bounds.x + bounds.width <= 391);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.waitForFunction(() => [...document.querySelectorAll('.synrhg-card img')].slice(0, 2).every(image => image.complete && image.naturalWidth > 0));
    await page.screenshot({ path: path.join(output, "gallery-mobile.png") });
    await page.getByRole("button", { name: "关闭画廊", exact: true }).click();
    await page.waitForSelector(".synrhg-dialog", { state: "detached" });
    report.push("PASS: 390px mobile viewport no horizontal overflow; close button");

    failList = true;
    await page.click("#open");
    await page.waitForSelector(".synrhg-retry");
    failList = false;
    await page.getByRole("button", { name: "重试", exact: true }).click();
    await waitCards();
    await page.keyboard.press("Escape");
    await page.waitForSelector(".synrhg-dialog", { state: "detached" });
    report.push("PASS: list request failure shows error; Retry reopens and loads");

    failThumb = true;
    await page.reload();
    await page.waitForFunction(() => window.ready);
    await page.click("#open");
    await waitCards();
    await page.waitForSelector(".synrhg-placeholder");
    assert.equal(await visibleCards(), 200);
    report.push("PASS: missing thumbnail shows placeholder without blocking preset selection");
    assert.deepEqual(errors, []);
    assert(!requests.some(url => /favs|favorite|openapi/.test(url)));
    report.push("PASS: no JavaScript errors, favorites requests, or generation requests");
    fs.writeFileSync(path.join(output, "browser-report.json"), JSON.stringify({ host: "minimal ComfyUI stub, real Chromium", checks: report }, null, 2));
    console.log(report.join("\n"));
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
