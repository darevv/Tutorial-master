---
name: tut
description: Make narrated tutorial videos of any app: an iOS app or mobile web app in the iPhone simulator (simctl + Maestro), or a web app in Playwright. Every tap is shown and said out loud, with a cloned voiceover, captions and a HyperFrames render. Asks how tech-savvy the audience is (that sets the pace), explores the codebase and offers a checkbox menu of videos. Use when the user types /tut, asks for a tutorial or how-to video, or wants a tutorial re-cut.
---

# /tut: narrated app tutorials

`SK=~/.claude/skills/tut/scripts`. Output goes in the current repo: `tutorial/<slug>.mp4`, project files in `tutorial/<slug>/`, settings in `tutorial/tut.json`, project notes in `tutorial/tut.md`.

## 0. Start-up (every time /tut runs)

1. **Read the project's notes first.** Read `tutorial/tut.md` (status table, test accounts, gotchas) and `tutorial/tut.json` if they exist. Project rules there (test accounts, privacy, what counts as real data) add to the hard rules below.
2. **Ask about the audience** with AskUserQuestion: "How comfortable with tech are the people watching?" If `tut.json` has an `audience`, offer it first as "(last time)". The answer sets the pace:

   | Audience | `speed` (voice) | `pace` (holds) | Narration |
   |---|---|---|---|
   | **Very new to tech** | 0.95 | 1.2 | Every tap shown and said, including closing the keyboard and scrolling. Say where the button is ("the blue button at the bottom"). One action per line. Repeat the key idea at the end. |
   | **Some comfort** (default) | 1.05 | 0.95 | Every tap shown and said, with short lines. |
   | **Comfortable** | 1.15 | 0.8 | Taps shown, and routine ones (keyboard, scroll) shown but not said. Lines can cover two actions; spend the words on *why*. |

   Save `audience`, `speed` and `pace` in `tutorial/tut.json`. `tts.py` and `build.py` read them; `SPEED` and `PACE` env vars override.
3. **Work out the platform** from the repo: an iOS app (`*.xcodeproj`, Expo/React Native), a web app (Next/Vite/React routes, `package.json` dev server), or both. A mobile-first web app can be recorded either way; ask which one if it's unclear. Web apps use Playwright (`web.js`). Read the playwright-skill for dev-server detection (`cd ~/.claude/skills/playwright-skill && node -e "require('./lib/helpers').detectDevServers().then(s=>console.log(JSON.stringify(s)))"`) or use the live URL the user gives you.
4. **Explore and offer a menu.** Use an Explore agent, or read the routes, pages, nav and main forms yourself. List the user-facing flows a tutorial could cover, each as a one-line "what the viewer learns". Leave out ones `tut.md` marks done unless a re-cut is asked for. Show them as **checkboxes**: AskUserQuestion with `multiSelect: true`, up to 4 questions of 4 options each, grouped by area (e.g. "Getting started", "Daily work", "Admin"). Recommend an order, starting with getting started / sign-in. Then make the picked videos one at a time and show the user each one.
5. **Settle test data before recording.** Ask which test accounts to use, or offer to create them (ask first). Write their names and roles in `tut.md`. Keep passwords and session files in `~/.config/tut/<project>/` and never echo or commit them.

## Hard rules

- **Never act on a real person.** Every write (create, edit, delete, send, pay) happens only on test accounts or test data. Treat any account you didn't create as real. Real people may appear in lists; blur private data (ffmpeg `boxblur` on the clip).
- **Confirm with the user before** any write that isn't on test data, and before anything that emails, texts or notifies people. Never tick "notify/email" boxes on camera unless the user says so.
- **Bugs and UX gaps** you notice go in `tutorial/bugs/NN-short-name.md` (what happens, where, what was expected, where to look in the code). List them in your summary. Don't fix app code unless asked.
- **One consistent voice.** Every line is cloned from one reference clip: `voice-ref.wav` + `voice-ref.txt` in this skill ("The Podcaster"), or the `voice_ref` path in `tut.json`, with a `.txt` transcript beside it. Never generate with plain seeds or instructions, because each seed sounds like a different person. Don't change the reference files. VoiceStudio must be running at `localhost:3900`; if it's down, ask the user to start it.
- **Humor is light and professional.** Use warm interjections ("Oh!", "Yay!", the occasional `[laughter]`) and at most one or two gentle jokes per video. No jokes about people, bodies or the audience's skill level. Test data is just "made up for this video".
- **Pronunciation:** for a brand name or foreign term, add a speech-only respelling in `tut.json` `"say": [["regex","Respelling"]]` (captions keep the real spelling). Render 3–4 candidates, play them with `afplay` and let the user choose by ear.
- **Look:** captions on, dark background, screen centred, title card, yellow tap rings, no music. Phone footage renders at 1080×1920 and desktop web at 1920×1080. `tut.json` `"subtitle"` is the small line under the title.

## Pipeline (one video)

`W=tutorial/<slug>` (`mkdir -p $W/shots`).

1. **Plan.** Read the UI code for the flow, and the server routes to see what each button writes or sends. Dry-run the flow first and note what's on each screen.

2. **Record.**
   - **Simulator** (iOS app or mobile Safari): record one clip per action, never one long take (simctl timestamps drift).
     `zsh $SK/step.sh $W <name> tap X Y` · `type "text"` · `swipe X1 Y1 X2 Y2` · `key Enter`. Coordinates are in the 460×1000 space of `$SK/shot.sh $W/shots/x`. Env: `TUT_DEVICE` (simulator UDID, default iPhone 17 `C9D73B92-…`), `TUT_APP` (bundle id, default Safari). Stay on one simulator and don't boot or shut others.
     **Take a screenshot right before every step.** When idle, the simulator falls back to the home screen, and Maestro then reopens the app and still taps, which once caused an irreversible action in a discarded take. Re-running a step name replaces that take. If a one-shot action happened off camera, splice a still of the "before" screen (`tpad`) ahead of the "after" clip. The first keyboard use per boot shows an iOS tip: dismiss it before recording.
   - **Web** (Playwright): write `$W/flow.json` (format at the top of `$SK/web.js`): url, `viewport` `desktop` (1280×720) or `mobile` (390×844), optional `storageState` for a signed-in session, off-camera `setup` steps, and `steps` that use selectors (`text=Save`, `#id`, `role=button[name="Save"]`). Run `node $SK/web.js $W`. It records one take, cuts it into per-step clips, and saves `shots/<step>.png` after each step: **look at them**. Each run replays the whole flow, so its writes happen again; reset test data or make the flow safe to re-run. To save a login session: sign in with a short Playwright script and `context.storageState({path})` into `~/.config/tut/<project>/`.

3. **Script**: `$W/script.json` is `[["intro","Hi! ..."], ["<step name>","Tap ..."], ..., ["outro","... See you in the next one!"]]`. Write one line per step, said *before* the action (it plays over the pre-tap screen; `build.py` freezes that frame if the line is longer). Name the button exactly as it appears on screen and say where it is. Match the narration rules for the chosen audience.

4. **Voice**: `python3 $SK/tts.py $W` prints OK/BAD and what Whisper heard for each line. Re-run the BAD ones with `SEEDS=5,17 python3 $SK/tts.py $W <key>`.

5. **Build**: `python3 $SK/build.py $W "<Title>"`, then `cd $W && npx hyperframes lint` (0 errors; the title sub-composition warning is fine).

6. **Verify**: run `npx hyperframes snapshot --at <tap times printed by build + 0.15> --no-end -o <scratch dir>` and look at each frame. The ring must sit on the right button **before** the screen changes, and captions must fit in 2 lines.

7. **Render**: `npx hyperframes render -o ../<slug>.mp4` (about 1 minute per minute of video), then `open` it. Tell the user what's in it, what test data it created or left behind, and which bugs you filed. Update the status table in `tutorial/tut.md`.
