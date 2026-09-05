# Case study: porting the pipeline to Android

**Setting.** The pipeline had run on iOS only. A client commissioned an Android arcade game
(Kotlin + Jetpack Compose). The game itself shipped to Google Play and is under NDA; what
is public here is the *port* — the rulebook chapter, the three workflows, the audio tool,
and what changed in the system to support a second platform.

## What "porting" meant

Not a rewrite of the orchestration: the queue, runners, gates and hooks are
platform-agnostic. The port was three things:

1. **A platform rulebook** — [`rulebook/android-games.md`](../rulebook/android-games.md).
   Written during the first build from the operator's corrections, in the same
   symptom → cause → invariant form as the iOS chapters. It covers the Compose
   architecture roles, the `withFrameNanos` game loop with a dt clamp, world units in
   metres, honest-gameplay arithmetic, designer-asset integration (bounding-box
   measurement before layout), and Play Store packaging.
2. **Three workflows** — [`workflows/droid-game.md`](../workflows/droid-game.md) (build from
   a flow sample or spec), [`workflows/droid-assets.md`](../workflows/droid-assets.md)
   (integrate designer assets), [`workflows/droid-pack.md`](../workflows/droid-pack.md)
   (clean build, zip without build products, store listing). Same shape as the iOS
   `/auto` → `/polish` → packaging chain.
3. **A tool** — [`tools/soundgen.py`](../tools/soundgen.py): every sound effect and the
   music loop are generated from formulas in the standard library, so a game ships with
   original audio and no licensed files.

## What the agent got wrong on Android, and the rule that followed

| Observed | Rule (now in `android-games.md`) |
|---|---|
| `targetSdk 35` — Play Console rejected the upload at submission: "must target at least API level 36" | compile/target SDK 36 is a hard constant; a rejected upload still consumes the versionCode, so every re-upload increments it |
| Scene scaled from *screen height*; characters stretched on tablets | scenes scale from an explicit unit `u = character height` chosen by the caller; the world uses `pxPerM = width / 15` |
| Arm length computed as a fraction of screen width — limbs stretched on wide screens | body parts are attached to their props in `u` units, arm length clamped |
| Obstacle taller than the jump apex — an unwinnable spawn | every obstacle height < `v²/2g`; spawn worst case must be passable on paper |
| Designer PNGs with huge transparent margins broke layout | measure the alpha bounding box, crop before layout, derive aspect ratios from cropped sizes |
| Moving parts baked into a static asset (needle, carriage) | movable parts are drawn natively; static assets are cut so that logic zones and visual zones share one axis variable |
| Agent installed the app on an emulator to "test", burning the first-launch flag | agents never launch the app; the operator tests on prepared emulators |

## Numbers

| | |
|---|---|
| calendar time from spec to Play-ready build | 2 days (03–04 Sep 2026) |
| Kotlin | ~3,700 lines across 16 files |
| rulebook chapter written during the build | 126 lines |
| workflows added | 3 |
| iOS rules reused | orchestration, gates philosophy, originality axes; none of the SwiftUI layout rules applied |

## Why this matters for the system

The port took one iteration because roles, gates and the definition of done were already
formalised; only the platform knowledge had to be written down. That is the argument for
keeping platform rules separate from pipeline rules — and the reason the iOS chapters say
"do not apply to Android" at the top.
