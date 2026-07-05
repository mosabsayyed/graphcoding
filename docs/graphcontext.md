# GraphContext — the boot is a query, not a recital

**GraphCode governs what the system IS. GraphContext governs what a fresh agent session must KNOW — and it is the prerequisite.** An agent booted from a bloated, rotting instructions monolith second-guesses the graph, re-derives stale conventions, and drowns the design signal in noise. Clean context isn't a nicety; it's what makes coding-to-the-graph possible at all.

## The disease: the monolith

Every agent team grows one — a CLAUDE.md / AGENTS.md that starts as ten crisp rules and swells into a scroll of laws, project status, step-by-step recipes, dispatch tables, and dates. It rots exactly the way architecture docs rot, for the same reason: **it mixes four kinds of knowledge with four different lifecycles into one file with none.**

Ask three questions of any line in your monolith:

1. *Statusless and load-bearing?* → **Constitution.** Identity, hard laws, pointers. The only content that belongs in the always-loaded file.
2. *Has a lifecycle — can it become done, stale, superseded?* → **State.** Belongs in the context graph, where a status can be flipped.
3. *Is it a verb — a procedure followed while doing X?* → **Skill.** Loaded on demand, not at boot.
4. *Is it about which of the above to load, and when?* → **Trigger data.** Dispatch tables are graph edges wearing a prose costume.

`graphcoding ctx cleanse CLAUDE.md` prepares this audit — it splits the blocks, surfaces mechanical *signals* (dates, tables, numbered steps) as hints, and prints the rubric. **The classification itself is the agent's semantic judgment, deliberately not the tool's**: block-classification cannot be honestly encoded as patterns, and a tool that pretends otherwise ships fraudulent confidence. The agent judges each block per the rubric and records the moves with `ctx add`. (Run agent-led on the production file this was extracted from: 13 blocks → 10 constitution; a state block, a dispatch table, and an embedded procedure moved out.)

## The cure: context as a graph with lifecycle

The context graph is the same JSONL family as the code graph — one JSON line per node, sorted, diffable, mergeable — with a tolerated markdown header, so **your agent's existing memory index file can simply *become* the graph** (same name, same load path, new powers):

```json
{"name": "rule_no_fakery", "type": "rule", "status": "active", "load": "always",
 "hook": "No done-claims without pasted real output"}
{"name": "proj_launch", "type": "project", "status": "active",
 "hook": "Ship v1; PyPI + announcement pending",
 "edges": [{"to": "rule_no_fakery", "type": "REFERENCES"}]}
```

- **`status`**: `active | done | retired`. Retired knowledge *stops loading everywhere at once* — no hunting its mentions across three files (the classic failure: a dead ritual documented in one place, still preached in another).
- **`load`**: `always`, `role=architect`, `task=frontend`, or `demand`. What today is hardcoded in your boot script becomes data.
- **`hook`**: the one-line recall cue — the only thing boot loads. Detail stays in per-memory files, fetched on demand.
- **Edges**: relations, including edges to nodes that don't exist yet — **memories owed**. Prospective memory is first-class here exactly as planned files are in GraphCode: humans remember the future, so should agents.

## The walker: `ctx boot`

```bash
graphcoding ctx boot --role architect --task frontend
```

Emits a few hundred tokens: cornerstones first, always-rules, role/task-scoped entries, the active future layer (real open work only — because closed work was *flipped*, not forgotten), pending trigger hints, and the owed list. That replaces loading the whole monolith + full memory index into every session. Lightweight context, and *truthful* context: a boot can't recite anything retired, because boots are queries.

## The command symmetry (the whole interface)

| you need to… | code | context |
|---|---|---|
| know before acting | `query` / `show` | `ctx query` / `ctx show` |
| declare intent / record knowledge | `plan` | `ctx add` |
| close or kill | `sync` (auto) / `mark-delete` | `ctx done` / `ctx retire` |
| verify honesty | `drift` | `ctx health` |
| see the future layer | `status` | `ctx status` |
| start a session | — | `ctx boot` |
| escape a monolith | `init` (scan) | `ctx cleanse` |

Ten verbs total. That's the entire operating surface for both halves of the methodology.

## Deploying GraphCode? GraphContext is step zero

1. **`ctx cleanse` your monolith.** Keep the constitution (it should fit on a screen); every state block becomes a `ctx add`, every dispatch row a trigger node, every recipe a skill file.
2. **Graph your memory index.** Keep its filename and load path — add the header, convert entries to node lines. Nothing about *how* the agent finds its memory changes; everything about what memory can *do* changes.
3. **Maintain with five verbs.** New knowledge → `ctx add` (with edges — an unlinked memory is a snapshot, not knowledge). Work closes → `ctx done`. Practice dies → `ctx retire`. Session starts → `ctx boot`. Weekly → `ctx health`.
4. **Then adopt the code loop** ([lifecycle](lifecycle.md)) on a mind that boots clean.

## Field results (the production system this ships from)

Run against a real 209-memory agent setup, the graph audit found: 25% of memories orphaned (written, indexed, never related — snapshots), the most-cited rule split between a real file and a misspelled ghost twin, five "unwritten" memories that existed in a forked second memory folder, a dead inter-agent ritual still preached by the docs, and a future layer of 16 "open" projects of which the human arbiter confirmed **one** was actually open. Every one of those failure classes is structural to flat context — and every one is a one-line query or one-status flip under GraphContext.

## Honest limits

Same as the code side, stated plainly: statuses are flipped by minds, not magic — the graph makes truth *cheap to record and impossible to half-remember*, but a human (or agent) still closes the loop. Hooks can lie like any prose; `ctx health` finds hookless and orphaned nodes but can't verify meaning. And the boot output is a summary by design — agents must fetch detail on demand rather than trust a hook for specifics. The claim is not "context maintains itself"; it's "context finally has a write path cheaper than the rot." And one boundary is absolute by design: **deterministic tools here do enumeration, bookkeeping, and gating; every semantic judgment — classifying a block, writing a summary, confirming staleness — belongs to a mind (human or LLM). Wherever this product appears to automate judgment, read closer: it scaffolds it.**
