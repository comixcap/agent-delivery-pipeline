# agent-delivery-pipeline

**A multi-agent system that turns a client specification into a release-ready mobile app
build — and the quality gates that keep the agents honest.**

This is the sanitized public version of a pipeline I designed, built and operate as its only
user. Since March 2026 it has produced 700+ builds from client specifications (the
fingerprint registry holds 759 of them), running up to six Claude Code agent sessions in
parallel on one Mac, with a Telegram front-end and no human in the loop between "spec
received" and "build succeeded, ready for a human test".

What is in this repository is the *system*: orchestration, roles, policies, gates, the
self-improvement loop, and a retrieval + eval harness over the rulebook. What is not here:
client specs, the reference project the agents copy infrastructure from, and the full
rulebook (two chapters are included as samples).

```
spec (Telegram / URL / file)
   │
   ▼
┌──────────────┐    queue/pending/*.md     ┌──────────────────┐
│  dispatcher  │ ───────────────────────▶  │   build-runner   │  launchd, every 120 s
│ (agent, TG)  │                           │  (dispatch only) │
└──────────────┘    queue/tasks/pending/   └────────┬─────────┘
   │                                                │ spawns ≤ N
   │                ┌──────────────┐       ┌────────▼─────────┐
   └──────────────▶ │ task-runner  │       │    build-one     │  one process per build
                    │ (fast lane)  │       │ 1 scaffold       │
                    └──────────────┘       │ 2 /auto  (agent) │
                                           │ 3 /polish (agent)│
        Stop hook: fix-journal             │ 4 registry check │
        SessionStart hook: learn-pending   │ 5 xcodebuild +   │
        03:30: learn-nightly (agent)       │   preflight gate │
        09:00: morning-brief               └────────┬─────────┘
                                                    ▼
                                  queue/done | failed | waiting (agent asked a question)
```

## Why it exists

The bottleneck in AI-assisted delivery was never typing code. It was *consistency*: the
same agent that builds a correct screen on Monday narrows the spec on Tuesday, invents an
API on Wednesday, and declares a bug fixed on Thursday without changing a line. Reviewing
every output by hand does not scale past a couple of builds a day.

So the system does three things a chat window cannot:

1. **Puts every agent inside a rulebook** — codified architectural invariants, loaded by
   task type, each written after a specific defect and stating how to prevent it, not how to
   patch it. See [`rulebook/`](rulebook/) for two chapters and
   [`workflows/`](workflows/) for five of the 41 reusable command workflows.
2. **Gates every handoff with checks that do not use an LLM** — a compile, a static
   analysis script, and a fingerprint comparison against every previously built app. An
   agent cannot talk its way past a grep. See [`gates/`](gates/) and the
   [failure catalog](docs/failure-catalog.md) for which gate catches which agent mistake.
3. **Learns from the operator's hands** — a session hook journals the edits I make manually
   after an agent, a nightly agent turns them into proposed rules, and I approve or reject.
   The rulebook grows from real defects with a human in the approval loop.

## Layout

| Path | What |
|---|---|
| `bin/dispatcher` + `policy/dispatcher-role.md` | the always-on Telegram agent: classifies, queues, never executes long work |
| `bin/build-runner`, `bin/build-one` | build lane: dispatch + one process per build, five stages, git snapshot after each |
| `bin/task-runner` | fast lane: store-review replies, recolors, targeted fixes; two in parallel |
| `bin/fix-journal`, `bin/learn-nightly`, `bin/learn-pending` | the self-improvement loop (Stop hook → journal → nightly proposals → SessionStart reminder) |
| `bin/morning-brief`, `bin/pipe`, `bin/spec-fetch` | digest, operator CLI, spec ingestion from URLs |
| `policy/allow-tools.txt`, `policy/deny-tools.txt` | tool policy for every agent session: no network, no store submission, no force push, no simulator |
| `policy/hooks.settings.json` | Claude Code hook wiring |
| `gates/preflight.sh` | 11 sections of mechanical checks; every FAIL blocks handoff |
| `gates/printcheck.py` | app fingerprint (type names, file names, keywords, privacy text, bundle ID) vs. the registry |
| `launchd/` | five background agents and why `AbandonProcessGroup` matters |
| `rag/` | BM25 retrieval over the rulebook + eval harness (hit@k, MRR, abstention) |
| `docs/failure-catalog.md` | agent failure classes observed in production and the gate for each |

## Design decisions worth defending

**Files, not a framework.** Queues are directories, state transitions are `mv`, claims
are atomic because `mv` is. For one operator on one machine this is more observable than
LangGraph or Temporal: `ls queue/running` is the dashboard. The runner/worker split,
per-build logs, and per-build lesson files are exactly the shape a framework would impose;
they are just visible.

**The dispatcher never works.** Its role prompt has one law: anything longer than a minute
goes into a lane. Otherwise the operator loses contact for the duration of a 90-minute
build. Latency of the human channel is a hard requirement; throughput belongs to the
runners.

**Parallel agents must not pick the same design.** Six concurrent builds reading one
registry will honestly choose the same palette and tab layout. A distributor pass assigns
divergent axes *before* dispatch, and each build writes a per-session claim file; the later
claimant yields on collision. This is a store-review requirement (apps from one account
are compared for similarity), turned into a scheduling constraint.

**"Done" is a file, not a sentence.** A build is done when `queue/done/` holds the spec,
the log says `BUILD SUCCEEDED`, and preflight has run twice. An agent session ending with
"all set!" is not evidence of anything — `build-one` explicitly checks whether the agent
stopped to ask a question and exited successfully with an empty skeleton.

**Fetched text is data.** Specs arrive from web pages. Instructions inside them addressed
to the agent are shown to the operator, not executed. The deny list makes the expensive
mistakes (network egress, store upload, `git push`) impossible rather than discouraged.

**Simulators are off-limits to agents.** An agent that "tests" the app walks through
onboarding and leaves a flag in the simulator's preference cache that survives reinstall;
the human tester then never sees onboarding. `simctl` is on the deny list and `build-one`
scrubs the cache anyway.

## Retrieval over the rulebook (`rag/`)

Agents load rules by task type; a symptom-driven lookup ("rings in a row overlap") is the
next step. `rag/` is a zero-dependency BM25 retriever over heading-and-rule chunks, with a
bilingual tokenizer (Russian rules, English/Russian queries, camelCase identifiers), an
optional Claude API answer step that must cite rule ids and is told to abstain, and an eval
set of 26 in-scope symptoms plus 3 out-of-scope questions.

```
$ cd rag && python3 -m rulebook_rag.index build ../rulebook index.json
chunks: 41  median chars: 255  max: 1863
$ python3 -m rulebook_rag.evaluate index.json evalset.json
in-scope cases: 26
hit@1 0.923   hit@3 0.962   hit@5 1.0   MRR 0.946
lowest top-1 score among in-scope hits: 2.84
out-of-scope top scores: 0.00  0.00  0.00
```

BM25 is the honest baseline for a corpus of a few hundred rules in one author's vocabulary,
and it runs offline inside a build where network is denied. The eval harness exists so that
"switch to embeddings" becomes a measured decision, not a fashion one.

## Numbers

| | |
|---|---|
| builds through the pipeline since 2026-03 | 700+ (759 fingerprints registered) |
| concurrent agent sessions | up to 6 builds + 2 fast-lane tasks |
| rulebook | ~900 lines of invariants + 41 workflows (~3,500 lines) |
| mechanical gates | 11 preflight sections, 6 fingerprint comparisons, 1 compile |
| background agents | 5 launchd jobs, 2 Claude Code hooks |
| tool policy | 17 denied command patterns |

## Scope, stated plainly

Single-operator system. I am its only user. What generalises: the rulebook discipline,
the workflow library, the non-LLM gates, the definition-of-done, the self-improvement
loop. What would need real work for a team: multi-tenancy, per-engineer preferences,
onboarding, and replacing launchd + files with something a second machine can join.

## Running it

Requires macOS, Xcode, [Claude Code](https://docs.anthropic.com/en/docs/claude-code), and
optionally a Telegram bot token. Set `PIPELINE_ROOT`, copy `policy/hooks.settings.json`
into `~/.claude/settings.json`, install the launchd agents from `launchd/README.md`. The
`/auto`, `/polish`, `/distribute`, `/ledger-recheck` workflows referenced by `build-one`
are project-specific command files; five representative ones are in `workflows/`.

## How this was built

With Claude as a coding partner, under the same rules the pipeline enforces on itself.
Architecture, policies, thresholds and the failure catalog are mine; they come from three
years of reading agent output like an engineer whose own codebase breaks when the agent is
wrong.

MIT — see [LICENSE](LICENSE).
