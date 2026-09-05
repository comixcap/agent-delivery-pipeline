# Agent failure catalog

Every class below was observed in production builds, more than once. For each: what the
agent does, how it looks from the outside, and which part of the system catches it. The
principle throughout: if a failure can be caught without an LLM, it is caught without an LLM.

| # | Failure class | How it presents | Caught by |
|---|---|---|---|
| 1 | **Silent scope narrowing** | Spec lists 14 screens, agent builds 9 and reports success. The omitted ones are the hard ones. | Spec saved verbatim to `REQUIREMENTS.md` before any code (survives session cleanup); `/check-tz` workflow re-reads it screen by screen; preflight §10 fails without it. |
| 2 | **Stopping with a question in headless mode** | The agent is *required* to ask when a spec collides with the registry. Headless, nobody answers: it prints the question and exits 0 on an empty skeleton. | `build-one` counts source files after `/auto`; < 8 files → spec moved to `queue/waiting/`, operator answers with `pipe answer`, the SAME session resumes via `--continue`. |
| 3 | **"Fixed" with the same bug** | Agent announces the fix; the diff is empty or touches something else. | Git snapshot after every stage; preflight runs before AND after polish; per-build `lessons.d/*.tsv` records what still fails. |
| 4 | **Invented API or symbol** | An iOS 17 modifier on an iOS 16 target; an SF Symbol name that does not exist (renders blank, no error). | `xcodebuild` gate for the former; `/fix-icons` workflow validates symbol names against the platform catalog for the latter. |
| 5 | **Placeholder logic** | `TODO`, "coming soon", `Button {}` with no action, `lorem ipsum` in demo data. | preflight §1 (`grep`). Zero tolerance: FAIL blocks handoff. |
| 6 | **Crash sources** | Force unwraps, `try!`, `Int(nan)` at display time, division by a `geo.size.width` that is 0 on first layout. | preflight §1 (unwrap regex); rulebook invariants for NaN sanitising at the display boundary. |
| 7 | **Copying the reference too faithfully** | Agents told to "copy infrastructure" copy *names*. Type names land in the binary as mangled symbols → apps from one account look like one app. | `printcheck.py`: blacklist of reference vocabulary, ≥ 6 shared type names = FAIL, file-name and metadata overlap thresholds. |
| 8 | **Parallel agents converging on one design** | Six builds read the same "what's taken" registry, none sees the others, all pick the same palette / tab count. | Distributor pass assigns divergent axes before dispatch; per-session claim files (`claims`) with later-claimant-yields on collision. |
| 9 | **Following instructions inside data** | A spec fetched from a web page contains "ignore previous rules and…". | Dispatcher role: fetched text is data; instructions are shown to the operator. Deny list makes the expensive actions impossible regardless. |
| 10 | **Side effects while "testing"** | Agent launches the app in a simulator, walks through onboarding, leaves a preference flag that survives reinstall. Human tester never sees onboarding. | `simctl` on the deny list; `build-one` shuts simulators down and deletes the app's preference plist after every build. |
| 11 | **Layout that only works on the agent's mental device** | Content wider than the viewport → the whole scroll drags sideways; sizeless views (`Color`, gradients) as `ZStack` siblings inflate a cell to half the screen. | preflight §5 (unclamped `ScrollView`); rulebook root rules on width and sizeless views; arithmetic checks at 375 pt and iPad width instead of device runs. |
| 12 | **Performance regressions in decorative art** | `.blur`, `blendMode`, `repeatForever` on a scene that is repeated 12 times in a picker. | preflight §6. |
| 13 | **Same defect, next project** | A bug fixed by hand on Tuesday reappears on Thursday in a different app. | Stop hook journals manual edits; nightly agent proposes a rule; operator adopts; SessionStart hook nags until reviewed. |
| 14 | **Overclaiming completion** | "All done, ready for review!" with a failing build. | Definition of done is mechanical: file in `queue/done/` + `BUILD SUCCEEDED` in the log + preflight ran twice. |
| 15 | **Metadata hallucination** | Version `0.1`, "beta" in the UI, hardcoded version strings, permissions declared but unused. | preflight §2 and §3. |
| 16 | **Store-review compliance drift** | Hidden-feature patterns: region/locale branching, network code in an offline app. | preflight §3; rulebook invariants; zero network in the app AND zero network for the agent. |
| 17 | **Regressing accessibility** | Icon buttons without labels, fixed font sizes that ignore Dynamic Type. | preflight §8 thresholds. |

## What this catalog does not cover

Semantic quality — whether the app is *good*, whether the domain mechanic is deep enough —
is judged by dedicated audit workflows run as sub-agents (`check-uiux`, `audit`,
`check-42`). Those are LLM judgments and are treated as such: advisory, logged, not gates.
