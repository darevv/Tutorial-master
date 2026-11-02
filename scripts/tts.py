"""Render every line of <workdir>/script.json in The Podcaster voice and verify it by transcription.
usage: python3 tts.py <workdir> [key ...]      (SEEDS=11,3,13 env to change seeds)
script.json = [["intro","..."], ["<step name>","..."], ..., ["outro","..."]]
Tags like [laughter] [sigh] are performed, not read. Output: <workdir>/vo/<key>.wav
"""
import array, json, os, subprocess, sys, wave, urllib.request
URL = "http://localhost:3900"
VOICE = "female, young adult, high pitch, australian accent"   # VoiceStudio archetype "The Podcaster"
# Every line is CLONED from one reference clip so the voice never drifts between lines/videos
# (different seeds = audibly different people; user flagged that on video 8). Don't change these files.
import re
W = sys.argv[1]; only = set(sys.argv[2:])
# per-project settings: tutorial/tut.json (next to the <slug> workdirs)
CFG = os.path.join(os.path.dirname(os.path.abspath(W)), "tut.json")
CFG = json.load(open(CFG)) if os.path.exists(CFG) else {}
SK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_WAV = os.path.expanduser(CFG.get("voice_ref", f"{SK}/voice-ref.wav"))
REF_TXT = open(REF_WAV[:-4] + ".txt").read().strip()
SPEED = os.environ.get("SPEED", str(CFG.get("speed", 1.05)))   # set by the audience level
# respellings for speech only (captions keep the real spelling), e.g. [["shidduch","Shiddookh"]]
SAY = [(re.compile(a, re.I), b) for a, b in CFG.get("say", [])]
def spoken(t):
    for rx, rep in SAY: t = rx.sub(rep, t)
    return t
SEEDS = [int(x) for x in os.environ.get("SEEDS", "11,3,13,21,7").split(",")]
os.makedirs(f"{W}/vo", exist_ok=True)

def healthy(p):
    with wave.open(p) as w:
        n = w.getnframes(); d = array.array("h", w.readframes(n))
    if not n: return False
    zc = sum(1 for a, b in zip(d, d[1:]) if (a < 0) != (b < 0)) / n
    act = sum(1 for x in d if abs(x) > 1000) / n
    return act > 0.2 and zc < 0.25

def transcribe(p):
    r = subprocess.run(["curl", "-s", "-m", "60", "-X", "POST", f"{URL}/transcribe", "-F", f"audio=@{p}"], capture_output=True, text=True)
    try: return json.loads(r.stdout)["text"]
    except Exception: return ""

def words(s): return set("".join(c.lower() if c.isalnum() or c == " " else " " for c in s).split())

for key, text in json.load(open(f"{W}/script.json")):
    if only and key not in only: continue
    out = f"{W}/vo/{key}.wav"
    target = words(" ".join(t for t in text.replace("[", "]").split("]")[::2]))
    best = None
    for seed in SEEDS:
        subprocess.run(["curl", "-s", "-m", "300", "-X", "POST", f"{URL}/generate", "-D", f"{W}/vo/h.txt", "-o", out,
                        "-F", f"text={spoken(text)}", "-F", f"ref_audio=@{REF_WAV}", "-F", f"ref_text={REF_TXT}", "-F", f"seed={seed}",
                        "-F", "guidance_scale=2.0", "-F", f"speed={SPEED}", "-F", "language=English"])
        for l in open(f"{W}/vo/h.txt", errors="replace"):      # don't keep VoiceStudio history copies
            if l.lower().startswith("x-audio-id:"):
                try: urllib.request.urlopen(urllib.request.Request(f"{URL}/history/{l.split(':',1)[1].strip()}", method="DELETE"), timeout=10)
                except Exception: pass
        if os.path.getsize(out) <= 44 or not healthy(out): continue
        heard = transcribe(out)
        score = len(target & words(heard)) / max(1, len(target))
        if score >= 0.7: best = (seed, heard); break
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    print(f"{'OK ' if best else 'BAD'} {key:22s} {dur}s  heard: {best[1] if best else transcribe(out)}", flush=True)
