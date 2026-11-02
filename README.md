# Tutorial Master (`/tut`)

A [Claude Code](https://claude.com/claude-code) skill that makes **narrated tutorial videos of any app**.

Point it at a repo and it explores the app, offers a checkbox menu of videos, then records every tap, writes a script, clones a voiceover, adds captions and renders an MP4.

- **iOS app or mobile web app** in the iPhone Simulator (`simctl` + Maestro), or
- **web app** in Playwright (desktop or mobile viewport).
- Every tap is shown (yellow ring) and said out loud, in one consistent cloned voice.
- Asks how tech-savvy the viewers are, which sets the voice speed, pacing and how much is narrated.
- Never acts on real people: all writes go to test accounts or test data.

## Install

```sh
git clone https://github.com/darevv/Tutorial-master ~/.claude/skills/tut
```

The folder **must** be named `tut` and live in `~/.claude/skills/`. The scripts find each other through that path. Then, inside any app's repo, run `/tut` in Claude Code.

## Prerequisites

macOS only (uses `xcrun`, `sips`, `zsh`, `afplay`).

| Needed for | Requirement | Install |
|---|---|---|
| Everything | [Claude Code](https://claude.com/claude-code) | see its docs |
| Everything | `ffmpeg` + `ffprobe` | `brew install ffmpeg` |
| Everything | Python 3 with `numpy` | `pip3 install numpy` |
| Everything | Node.js 18+ (`npx`) | `brew install node` |
| Everything | [HyperFrames](https://hyperframes.heygen.com) CLI, used for `lint`, `snapshot`, `render` | fetched on first use by `npx hyperframes`; needs internet (the build loads GSAP from jsDelivr) |
| Everything | **VoiceStudio** running at `http://localhost:3900` (local voice-cloning TTS + Whisper) | see below |
| iOS / mobile Simulator | Xcode with an iOS Simulator device **booted** | App Store |
| iOS / mobile Simulator | [Maestro](https://maestro.mobile.dev) at `~/.maestro/bin/maestro` (needs Java 17+) | `curl -fsSL "https://get.maestro.mobile.dev" \| bash` |
| Web (Playwright) | [`playwright-skill`](https://github.com/lackeyjb/playwright-skill) installed at `~/.claude/skills/playwright-skill` with its `node_modules` | `git clone https://github.com/lackeyjb/playwright-skill ~/.claude/skills/playwright-skill` then follow its setup (installs Playwright + Chromium) |

You only need the **iOS** rows or the **Web** row, depending on what you record. Everything else is needed either way.

### VoiceStudio

`tts.py` talks to a local VoiceStudio server on port 3900. Start the app before step 4 of the pipeline and check:

```sh
curl -s localhost:3900/health     # should contain "status":"ok"
```

The endpoints used are `POST /generate` (voice-cloned speech from `ref_audio` + `ref_text`), `POST /transcribe` (Whisper, used to verify each line was spoken correctly), and `DELETE /history/{id}`. Any local server that exposes those three will work if you'd rather swap the TTS.

### Simulator device

The default device is the iPhone 17 simulator UDID hardcoded in `scripts/step.sh` and `scripts/shot.sh`. Yours will differ. Find it and export it:

```sh
xcrun simctl list devices booted
export TUT_DEVICE=<your-simulator-UDID>
export TUT_APP=<bundle id>        # optional; defaults to Safari (com.apple.mobilesafari)
```

## What's in here

| File | Purpose |
|---|---|
| `SKILL.md` | The skill itself: start-up questions, hard rules, and the 7-step pipeline |
| `scripts/step.sh` | Records one simulator step (tap / type / swipe / key) as its own clip |
| `scripts/shot.sh` | Screenshots the simulator in the 460×1000 coordinate space `step.sh` uses |
| `scripts/web.js` | Records a web flow described in `flow.json` with Playwright, cut into per-step clips |
| `scripts/tts.py` | Renders each script line in the cloned voice and verifies it by transcription |
| `scripts/build.py` | Assembles clips, voiceover and captions into a HyperFrames project |
| `voice-ref.wav` / `.txt` | The reference clip and transcript every line is cloned from ("The Podcaster", a VoiceStudio synthetic voice). Use your own by setting `voice_ref` in `tutorial/tut.json` |

## Output

Created inside the app's repo you run `/tut` from:

```
tutorial/
  <slug>.mp4        the finished video
  <slug>/           clips, script.json, voiceover, HyperFrames project
  tut.json          audience, voice speed, pacing, pronunciation respellings
  tut.md            status table, test accounts, gotchas
  bugs/NN-*.md      bugs and UX gaps noticed while recording
```

Logins and session files are kept in `~/.config/tut/<project>/`, never in the repo.

## Quick start

1. Start VoiceStudio. Boot a simulator (or start your web app's dev server).
2. In your app's repo, open Claude Code and type `/tut`.
3. Pick the audience, tick the videos you want, and review each one as it's made.

## License

[MIT](LICENSE)
