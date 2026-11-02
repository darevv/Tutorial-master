"""Assemble a tutorial from per-step clips into a HyperFrames project.
usage: python3 build.py <workdir> "<Title>"
reads  <workdir>/layout.json {"sw","sh"} = coordinate space of the clips (step.sh: 460x1000 sim, web.js: viewport)
       ../tut.json {"pace", "subtitle"}
reads  <workdir>/steps.txt   (written by step.sh, in recording order)
       <workdir>/script.json (intro, one line per step name [optional], outro)
       <workdir>/clips/<step>-cfr.mp4, <workdir>/vo/<key>.wav
writes <workdir>/assets/screen-edit.mp4, assets/vo/*.m4a, index.html
Then: cd <workdir> && npx hyperframes lint && npx hyperframes render -o ../<slug>.mp4
"""
import html, json, os, re, subprocess, sys
import numpy as np

W, TITLE = sys.argv[1], sys.argv[2]
CFG = os.path.join(os.path.dirname(os.path.abspath(W)), "tut.json")
CFG = json.load(open(CFG)) if os.path.exists(CFG) else {}
PACE = float(os.environ.get("PACE", CFG.get("pace", 0.95)))   # >1 = slower (more hold around each tap), set by the audience level
SUB = CFG.get("subtitle", "Tutorial")
L = json.load(open(f"{W}/layout.json")) if os.path.exists(f"{W}/layout.json") else {"sw": 460, "sh": 1000}
SW, SH = L["sw"], L["sh"]
GW = 67; GH = round(GW * SH / SW)        # motion-detection grid
# canvas: portrait 1080x1920 for phones, landscape 1920x1080 for desktop web; screen box + caption band below it
if SH >= SW: CW, CH, BH, OY, CAPH, FS, RAD = 1080, 1920, 1566, 40, 250, 46, 44
else:        CW, CH, BH, OY, CAPH, FS, RAD = 1920, 1080, 900, 24, 140, 40, 14
K = BH / SH; BW = round(SW * K); OX = (CW - BW) // 2; CAPY = OY + BH + 10
FPS = 30
g = lambda x: round(x * FPS) / FPS          # snap every cut to the frame grid (avoids drift)
script = dict(json.load(open(f"{W}/script.json")))
steps = [l.rstrip("\n").split("|") for l in open(f"{W}/steps.txt") if l.strip()]
os.makedirs(f"{W}/assets/vo", exist_ok=True)

def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True).stdout)
def vo(k): return dur(f"{W}/vo/{k}.wav") if k in script else 0.0
for k in script:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"{W}/vo/{k}.wav", "-c:a", "aac", "-b:a", "160k", f"{W}/assets/vo/{k}.m4a"], check=True)

def frames(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vf", f"scale={GW}:{GH}", "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, GH, GW).astype(np.int16)

INTRO = g(vo("intro") + 0.8)
segs, events, t = [], [dict(kind="voice", key="intro", start=0.3)], INTRO
for name, kind, a1, a2, a3, a4 in steps:
    src = f"{W}/clips/{name}-cfr.mp4"
    F = frames(src); tt = np.arange(len(F)) / FPS
    dg = np.zeros(len(F)); dg[1:] = np.abs(np.diff(F, axis=0)).mean(axis=(1, 2))
    if kind == "tap":   # first change near the tapped spot = moment the UI reacted
        x, y = int(float(a1) * GW / SW), int(float(a2) * GH / SH)
        p = F[:, max(0, y - 5):y + 6, max(0, x - 5):x + 6]
        dl = np.zeros(len(F)); dl[1:] = np.abs(np.diff(p, axis=0)).mean(axis=(1, 2))
        sig = np.maximum(dl, dg * 2)
    else:
        sig = dg
    hit = np.where((tt > 2.0) & (sig > (2 if kind == "tap" else 1)))[0]
    react = float(tt[hit[0]]) if len(hit) and kind != "wait" else 2.5
    if kind == "tap" and a3: react = float(a3)                     # steps.txt name|tap|X|Y|<react s>| pins the moment when pixel detection picks a later change
    v = vo(name); clipdur = len(F) / FPS
    need = max(0.8, v + 0.4 * PACE)                                # the whole line finishes before the tap; PACE scales only the pad (v*PACE overlapped lines at PACE<1)
    lead = min(need, react - 0.1)
    moved = np.where((tt >= react) & (dg > 0.3))[0]                 # last change while typing (none: password dots too small to see)
    post = (max(1.2, (float(tt[moved[-1]]) if len(moved) else react) - react + 0.9) if kind == "type" else 1.5) * PACE
    if kind == "wait": lead, need, post = 0.3, 0.3, clipdur - 0.6
    ms = g(react - lead); lead = react - ms
    hold = g(max(0.0, need - lead))                                # not enough pre-tap footage: freeze the clip's first frame
    total = g(hold + min(lead + post, clipdur - ms - 0.05))
    segs.append((src, ms, total, hold))
    lead += hold
    if v: events.append(dict(kind="voice", key=name, start=t + 0.15))
    if kind == "tap": events.append(dict(kind="tap", start=t + lead - 0.25, x=float(a1), y=float(a2)))
    if kind == "key" and a2: events.append(dict(kind="tap", start=t + lead - 0.25, x=float(a2), y=float(a3)))  # steps.txt: name|key|Enter|X|Y| (ring on the key)
    if kind == "swipe": events.append(dict(kind="swipe", start=t + lead - 0.45, x=float(a1), y=float(a2), x2=float(a3), y2=float(a4)))
    t += total; last = (src, g(clipdur - 0.2))
od = g(vo("outro") + 1.2)
segs.append((last[0], last[1], od, 0.0)); events.append(dict(kind="voice", key="outro", start=t + 0.2)); t += od
segs.insert(0, (segs[0][0], 0.0, INTRO, 0.0))                      # intro: hold first clip's opening frame
total_len = round(t, 2)

# --- cut the screen track ---
srcs = sorted({s for s, *_ in segs}); idx = {s: i for i, s in enumerate(srcs)}
# (segment 0 = intro: freeze the first frame instead of playing the clip)
fc = [f"[{idx[s]}:v]trim=start={a:.3f}:duration={0.04 if n == 0 else d - h:.3f},setpts=PTS-STARTPTS,tpad=start_mode=clone:start_duration={h:.3f}:stop_mode=clone:stop_duration=30,trim=duration={d:.3f}[v{n}]" for n, (s, a, d, h) in enumerate(segs)]
fc.append("".join(f"[v{n}]" for n in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[out]")
open(f"{W}/fc.txt", "w").write(";\n".join(fc))
subprocess.run(["ffmpeg", "-v", "error", "-y"] + sum([["-i", s] for s in srcs], []) + ["-filter_complex_script", f"{W}/fc.txt", "-map", "[out]",
                "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-g", "15", "-pix_fmt", "yuv420p", "-r", str(FPS), f"{W}/assets/screen-edit.mp4"], check=True)

# --- composition ---
clean = lambda s: re.sub(r"\s+", " ", re.sub(r"\[[a-z ]+\]", "", s)).strip()
clips, js = [], []
for n, e in enumerate(events):
    if e["kind"] == "voice":
        k, d = e["key"], vo(e["key"])
        clips.append(f'<audio id="vo-{k}" src="assets/vo/{k}.m4a" data-start="{e["start"]:.2f}" data-duration="{d:.2f}" data-track-index="2" data-volume="1"></audio>')
        chunks, cur = [], ""                                   # captions: <=90-char sentence chunks
        for s in re.split(r"(?<=[.!?])\s+", clean(script[k])):
            if cur and len(cur) + len(s) > 90: chunks.append(cur); cur = s
            else: cur = (cur + " " + s).strip()
        chunks.append(cur); tot = sum(map(len, chunks)); st = e["start"]
        for ci, c in enumerate(chunks):
            cd = d * len(c) / tot
            clips.append(f'<div id="cap-{k}-{ci}" class="clip cap" data-start="{st:.2f}" data-duration="{cd + (0.35 if ci == len(chunks) - 1 else 0):.2f}" data-track-index="3">{html.escape(c)}</div>')
            st += cd
    elif e["kind"] == "tap":
        x, y = OX + e["x"] * K, OY + e["y"] * K
        clips.append(f'<div id="tap{n}" class="clip ring" data-start="{e["start"]:.2f}" data-duration="1.0" data-track-index="4" style="left:{x - 55:.0f}px;top:{y - 55:.0f}px"></div>')
        js.append(f'tl.fromTo("#tap{n}",{{scale:0.4,opacity:1}},{{scale:1.4,opacity:0,duration:0.95,ease:"power2.out"}},{e["start"]:.2f});')
    else:
        x, y = OX + e["x"] * K, OY + e["y"] * K; dx, dy = (e["x2"] - e["x"]) * K, (e["y2"] - e["y"]) * K
        clips.append(f'<div id="sw{n}" class="clip dot" data-start="{e["start"]:.2f}" data-duration="1.4" data-track-index="4" style="left:{x - 34:.0f}px;top:{y - 34:.0f}px"></div>')
        js.append(f'tl.fromTo("#sw{n}",{{x:0,y:0,opacity:0.9}},{{x:{dx:.0f},y:{dy:.0f},duration:1.0,ease:"power1.inOut"}},{e["start"]:.2f});')
        js.append(f'tl.to("#sw{n}",{{opacity:0,duration:0.3}},{e["start"] + 1.05:.2f});')
nl = "\n      "
open(f"{W}/index.html", "w").write(f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={CW}, height={CH}" />
    <title>{html.escape(TITLE)}</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      body {{ margin: 0; background: #141414; color: #fff; font-family: system-ui, sans-serif; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: #141414; }}
      #screen {{ position: absolute; left: {OX}px; top: {OY}px; width: {BW}px; height: {BH}px; border-radius: {RAD}px; object-fit: cover; box-shadow: 0 0 0 3px #3a3a3a; }}
      .cap {{ position: absolute; left: 60px; right: 60px; top: {CAPY}px; height: {CAPH}px; display: flex; align-items: center; justify-content: center; font-size: {FS}px; line-height: 1.25; font-weight: 600; text-align: center; color: #fff; }}
      .ring {{ position: absolute; width: 110px; height: 110px; border-radius: 50%; border: 8px solid #ffd54a; background: rgba(255, 213, 74, 0.35); box-sizing: border-box; }}
      .dot {{ position: absolute; width: 68px; height: 68px; border-radius: 50%; background: rgba(255, 213, 74, 0.8); }}
      #title {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(15, 15, 15, 0.88); }}
      #title h1 {{ margin: 0 60px; font-size: 104px; font-weight: 800; text-align: center; line-height: 1.05; }}
      #title h2 {{ margin: 28px 0 0; font-size: 44px; font-weight: 500; color: #d9b45a; text-align: center; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="{CW}" data-height="{CH}" data-duration="{total_len}">
      <video id="screen" src="assets/screen-edit.mp4" muted playsinline data-start="0" data-duration="{total_len}" data-track-index="0"></video>
      <section id="title" class="clip" data-start="0" data-duration="{INTRO:.2f}" data-track-index="1">
        <h1 id="title-h1">{html.escape(TITLE)}</h1>
        <h2 id="title-h2">{html.escape(SUB)}</h2>
      </section>
      {nl.join(clips)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.fromTo("#title-h1", {{ y: 40, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "power3.out" }}, 0.2);
      tl.fromTo("#title-h2", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.6, ease: "power3.out" }}, 0.45);
      tl.to(["#title-h1", "#title-h2"], {{ opacity: 0, duration: 0.4 }}, {INTRO - 0.5:.2f});
      {nl.join(js)}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
''')
taps = [round(e["start"], 2) for e in events if e["kind"] in ("tap", "swipe")]
print(f"built {W}/index.html  length {total_len}s  steps {len(steps)}  tap/swipe times {taps}")
