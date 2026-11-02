// Record a web-app tutorial with Playwright: one take of the whole flow, cut into per-step clips
// with the same shape step.sh makes (2.5 s before the action, 2.5 s after), so build.py works unchanged.
// usage: node web.js <workdir>            reads <workdir>/flow.json, writes clips/, steps.txt, layout.json, shots/
// flow.json:
// { "url": "http://localhost:3000/loads", "viewport": "desktop" | "mobile",
//   "storageState": "~/.config/tut/<project>/<account>.json",   // optional, signed-in session (never commit)
//   "userAgent": "Mozilla/5.0 (iPhone; ...)",   // optional: pages that branch on the device
//   "dialogs": "accept",   // optional: press OK on confirm()/alert() (they don't show in the video, so say them)
//   "setup": [ steps, done off-camera before recording starts ],
//   "steps": [ {"name":"open-loads", "tap":"text=Loads"},
//              {"name":"type-ref",   "type":"#ref", "text":"ABC123"},     // click the box, then type it visibly
//              {"name":"type-pw",    "type":"#pw", "textFile":"~/.config/tut/<project>/x.txt"},  // secret: never in flow.json/steps.txt
//              {"name":"attach",     "upload":"input[type=file]", "file":"~/x.pdf", "ring":"text=Upload"},
//              {"name":"pick-addr",  "fill":"input[name=originStreet]", "text":"200 Sample Road, Edison NJ 08817"},  // = choosing a suggestion
//              {"name":"pick-role",  "select":"select[name=role]", "value":"dispatcher"},
//              {"name":"open-link",  "tap":"a[href*=\"/x/\"]", "sameTab":true},   // target=_blank link opened in the recorded tab
//              {"name":"enter",      "key":"Enter"},
//              {"name":"show-send",  "hover":"button:has-text(\"Send\")"},  // no click, no ring
//              {"name":"scroll",     "scroll":600},                        // px down (negative = up)
//              {"name":"go",         "goto":"http://..."} ] }
// Every run replays the whole flow, so any write it makes happens again: use test accounts / reset data first.
const { chromium } = require(process.env.HOME + '/.claude/skills/playwright-skill/node_modules/playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const W = process.argv[2];
const flow = JSON.parse(fs.readFileSync(`${W}/flow.json`, 'utf8'));
const VP = flow.viewport === 'mobile' ? { width: 390, height: 844 } : { width: 1280, height: 720 };
const home = p => p && p.replace(/^~/, process.env.HOME);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function act(page, s) {          // returns the ring point (viewport px) for taps
  if (s.wait) return void await page.waitForTimeout(s.wait);   // setup only: let a sign-in finish
  if (s.goto) return void await page.goto(s.goto);
  if (s.key) return void await page.keyboard.press(s.key);
  if (s.scroll) { await page.mouse.wheel(0, s.scroll); return; }
  if (s.hover) { const h = page.locator(s.hover).first(); await h.scrollIntoViewIfNeeded(); await h.hover(); return; }   // point at a button without pressing it (no ring)
  if (s.upload) {                       // file inputs are often hidden: ring the visible "ring" selector if given
    await page.locator(s.upload).first().setInputFiles(home(s.file));
    const r = s.ring && await page.locator(s.ring).first().boundingBox();
    return r && [Math.round(r.x + r.width / 2), Math.round(r.y + r.height / 2)];
  }
  const el = page.locator(s.tap || s.type || s.select || s.fill).first();
  await el.scrollIntoViewIfNeeded();
  const b = await el.boundingBox();
  const pt = b && [Math.round(b.x + b.width / 2), Math.round(b.y + b.height / 2)];
  if (s.select) { await el.selectOption(s.value); return pt; }
  if (s.fill) { await el.fill(s.text); return pt; }       // instant, like picking a datalist/autocomplete suggestion
  if (s.sameTab) await el.evaluate(e => e.removeAttribute('target'));   // keep a target=_blank link in the recorded tab
  await el.click();
  if (s.type) await el.pressSequentially(s.textFile ? fs.readFileSync(home(s.textFile), 'utf8').trim() : s.text, { delay: 70 });
  return pt;
}

(async () => {
  for (const d of ['clips', 'shots', 'raw']) fs.mkdirSync(`${W}/${d}`, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: VP, deviceScaleFactor: 2, userAgent: flow.userAgent, isMobile: flow.viewport === 'mobile', hasTouch: flow.viewport === 'mobile',
    storageState: home(flow.storageState), permissions: flow.permissions,   // e.g. ["clipboard-read","clipboard-write"]
    recordVideo: { dir: `${W}/raw`, size: VP },
  });
  const t0 = Date.now();                // ponytail: video starts ~at context creation; build.py finds the real tap moment from pixels
  const page = await ctx.newPage();
  if (flow.dialogs === 'accept') page.on('dialog', d => d.accept());   // confirm() boxes: headless never draws them, so narrate them
  const now = () => (Date.now() - t0) / 1000;
  await page.goto(flow.url);
  for (const s of flow.setup || []) await act(page, s);
  await page.waitForLoadState('networkidle').catch(() => {});
  const cuts = [];
  for (const s of flow.steps) {
    const start = now();
    // bring the target on screen at the start of the clip (visible smooth scroll), so the ring point is right
    const sel = s.tap || s.type || s.select || s.fill || s.ring || s.hover;   // hover too: its line plays over this view
    if (sel) await page.locator(sel).first().evaluate(e => { const r = e.getBoundingClientRect();
      if (r.top < 60 || r.bottom > innerHeight - 20) e.scrollIntoView({ block: 'center', behavior: 'smooth' }); }).catch(() => {});
    await sleep(2500);
    let pt; try { pt = await act(page, s); } catch (e) { console.log(`FAILED ${s.name} on ${page.url()}: ${e.message.split("\n")[0]}`); break; }
    await sleep(2500);
    await page.screenshot({ path: `${W}/shots/${s.name}.png` });   // look at these before writing the script
    cuts.push({ s, pt, start, end: now() });
    console.log(`recorded ${s.name}`);
  }
  const video = await page.video().path();
  await ctx.close(); await browser.close();

  // same coordinate space as the clips: viewport px
  fs.writeFileSync(`${W}/layout.json`, JSON.stringify({ sw: VP.width, sh: VP.height }));
  const lines = [];
  for (const { s, pt, start, end } of cuts) {
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', start.toFixed(3), '-t', (end - start).toFixed(3), '-i', video,
      '-vf', 'fps=30', '-c:v', 'libx264', '-crf', '18', '-preset', 'fast', '-g', '15', '-pix_fmt', 'yuv420p', '-an',
      `${W}/clips/${s.name}-cfr.mp4`]);
    const kind = s.tap || s.select || s.fill || (s.upload && pt) ? 'tap' : s.type ? 'type' : s.key ? 'key' : s.scroll ? 'scroll' : s.wait ? 'wait' : 'goto';   // wait: build.py keeps the whole clip (e.g. a streamed reply)
    lines.push(kind === 'tap' ? `${s.name}|tap|${pt[0]}|${pt[1]}||` : kind === 'type' ? `${s.name}|type|${s.textFile ? '(secret)' : s.text}|||` : `${s.name}|${kind}||||`);
  }
  fs.writeFileSync(`${W}/steps.txt`, lines.join('\n') + '\n');
  console.log(`cut ${cuts.length} clips → ${W}/clips (raw take: ${video})`);
})();
