# Brand Safety Lab (APRD 3002 — Brand Safety on X)

Student-facing interactive lab: judge post + ad adjacencies as SAFE or UNSAFE,
tag unsafe ones with a GARM category, export a CSV for Canvas submission.
15-minute timer, Identikey login, all state in browser localStorage.

Live: https://chrisjvargo.github.io/brand-safety-lab/

Static site, no build step. GitHub Pages serves this repo root.

## Provenance

Recovered Oct 2026 from the Spring 2026 AWS Elastic Beanstalk deployment
(`brand-safety-lab-prod`, since decommissioned). Source of truth:

- `1social_listening_cu/03_assignments/prompts/in_class_exercises/brand_safety_exercise/public/`

## Differences from the final Beanstalk bundle

1. `app.js` `resolveAsset` resolves assets relative to the page instead of the
   domain root, so the lab works under the `/brand-safety-lab/` project path.
2. `data/ads.json` points the Liquid Death ad at the new
   `media/ads/liquiddeath-mango.svg` creative; the shipped
   `media/ads/liquid-death.jpg` was a 29-byte 404 stub in every Beanstalk
   build (image search failed at build time) and is excluded here.
3. Eight media files missing from the working copy were restored from the
   final Beanstalk app zip before staging.
4. `.nojekyll` disables Jekyll processing on Pages.
5. `tests/lab.flow.test.mjs` (`npm test`, needs `npm i` once) drives the real
   `app.js` in jsdom: login, both feed batches, safe/unsafe judging, GARM
   dialog, hints, blur, references, analytics, CSV export, reset, timer.
6. 217 unreferenced spare images (~51 MB) were pruned from this repo; the
   instructor source keeps them.

## UI/UX debug fixes (Oct 2026, mirrored to instructor source)

- Removed `trimHistory`: it deleted judged feed items once 48 nodes passed the
  36-node cap, with no way to get them back.
- The 15-minute timer now starts at login instead of page load.
- CSV export is blocked until at least one placement is judged, and the file
  is named `<identikey>-<timestamp>.csv` so submissions map to students.
- Student-facing copy: dropped "facilitation notes" (no such feature) and the
  "local mirror" builder note.

## Real ads + pairing gold (Oct 2026)

- All 24 ads embed the actual creative file from `kai_ctr`
  `creative_sample_50.zip` (15 photos + 9 short videos, web-sized by
  `tools/build_sample50_ads.py` into `media/ads/real/`). Copy is the
  matched Meta Ad Library body where it verifiably fits the visible
  creative, otherwise transcribed from the creative itself. Selection
  in `tools/sample50_manifest.json`. No panel outcomes ship here.
- Gold standard is per post+ad pairing (`data/answer_key.json` keys are
  `postId__adId`): Floor posts block for every brand; suitability calls
  follow each brand's type (charity/kids strict, mainstream managed,
  playful/entertainment tolerant), explained in the feedback note.
- Timer is 15 minutes, auto-starting at login (in class, Dr. Vargo runs
  the room timer; async students follow the on-screen timer).

## Run locally

```sh
python3 -m http.server 8137
# open http://127.0.0.1:8137/
```
