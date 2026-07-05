# The full memory architecture for coding agents

GraphCoding is **not** the whole memory of a coding agent, and claims to the contrary should make you suspicious of any tool. Agent memory is four different problems wearing one name. Teams keep buying one layer and expecting the other three; then "memory" disappoints and gets blamed as a category.

This page separates the concerns — what each layer remembers, what question it answers, what happens when you misuse it for a neighbor's job — and shows where GraphCoding sits: the layer that was missing, not the layer that replaces the rest.

## The four layers

```
┌──────────────────────────────────────────────────────────────────────┐
│ 4 · VERIFICATION MEMORY      types · tests · CI                      │
│     remembers: what the system must DO (behavior, contracts)         │
│     answers:   "does it still work?"                                 │
├──────────────────────────────────────────────────────────────────────┤
│ 3 · DESIGN-STATE MEMORY      ★ GraphCoding                           │
│     remembers: what the system IS and SHOULD BECOME —                │
│     every unit's intent, wiring, lifecycle (planned/ok/doomed)       │
│     answers:   "what exists? who breaks? what's left? what dies?"    │
├──────────────────────────────────────────────────────────────────────┤
│ 2 · EPISODIC MEMORY          decision logs · session digests ·       │
│                              memory files/servers (MCP, notes)       │
│     remembers: what HAPPENED — choices made, approaches that failed, │
│     gotchas, the why behind the graph's what                         │
│     answers:   "have we been here before? why is it like this?"      │
├──────────────────────────────────────────────────────────────────────┤
│ 1 · RETRIEVAL MEMORY         embeddings · code search · LSP indexes  │
│     remembers: nothing durable — derived views, rebuilt at will      │
│     answers:   "where is the thing shaped like my question?"         │
└──────────────────────────────────────────────────────────────────────┘
```

### Layer 1 — Retrieval (find things)

Search indexes, embeddings, RAG over code, LSP databases. Fast lookup over content that already exists. Everything here is **derived and disposable** — delete it, rebuild it, nothing is lost.

*Misuse pattern:* treating retrieval as truth. A RAG hit tells you a chunk is *similar to your question*, not that it's current, complete, or load-bearing. Retrieval finds candidates; it cannot vouch for them.

### Layer 2 — Episodic (remember what happened)

Decision records, session digests, "we tried X and it deadlocked", per-project memory files or memory servers. This is **narrative** memory: unstructured, human/agent-written, append-mostly. Its value is the *why* — the reasoning that no artifact carries.

*Misuse pattern:* stuffing structure into it ("file A calls file B" as a prose note). Narrative rots silently because nothing checks it; structural facts written as prose are stale the day after they're written. Structure belongs one layer up, where a gate can defend it.

### Layer 3 — Design-state (the contract) ★ this project

What exists, what it's *for*, how it's wired — **and the future**: what's planned, what's condemned. Structured, versioned with the code, and *enforced*: commits are blocked while code and declared state disagree ([drift](drift.md)).

This is the layer that didn't exist as a discipline. Everyone has layers 1, 2 (however messy), and 4. The design contract lived in heads, tickets, and stale diagrams — precisely the memory whose absence makes agents edit blind, creep scope, and abandon refactors halfway.

*Misuse pattern:* expecting it to remember *why* (that's layer 2) or to prove *behavior* (that's layer 4). The graph records that `invoices.py` should exist and who may call it; it does not record the meeting where you chose invoices over receipts, nor whether the tax math is right.

### Layer 4 — Verification (defend behavior)

Types, tests, CI. Remembers the system's *obligations* at function-and-behavior granularity and re-checks them mechanically on every change.

*Misuse pattern:* believing green tests mean the *design* is intact. Tests pass happily in a repo where half a refactor was abandoned, dead modules accumulate, and the architecture no one wrote down has quietly inverted. Verification memory has no opinion about shape, intent, or the future — layer 3 does.

## The division of labor, sharply

| Question | Layer that owns it |
|---|---|
| "Where's the code that handles refunds?" | 1 · retrieval |
| "Why do refunds go through the queue instead of inline?" | 2 · episodic |
| "What breaks if I change the refund service?" | 3 · **GraphCoding** |
| "What is this file *for*?" | 3 · **GraphCoding** |
| "What's left to build / scheduled to die?" | 3 · **GraphCoding** |
| "Did my change break refund behavior?" | 4 · tests |
| "Is this function's new signature compatible?" | 4 · types |

Two boundary rules that keep the layers honest:

- **Structure flows up, never sideways.** A structural fact discovered in conversation (layer 2 territory) gets *recorded* in layer 3 (`graphcoding link`), where the gate defends it. Episodic memory keeps the story; the graph keeps the fact.
- **Granularity splits 3 and 4.** GraphCoding is deliberately unit-grained (files, opt-in symbols): the architecture view. Function-signature and behavior granularity belongs to types and tests, which check it better than any graph could. Asking the graph "is this call still type-safe?" is as wrong as asking the compiler "should this module exist?"

## What this architecture says about GraphCoding's own failure modes

Being explicit about which known weaknesses are *ours to fix* and which are *the neighbor layer's job*:

| Failure mode | Verdict |
|---|---|
| Summaries go stale while structure stays clean | **Ours.** `graphcoding health` now detects stale-summary suspects (stored summary vs the file's own current self-description) and names them. The gate defends structure; health surveils meaning. |
| Unrecorded cross-boundary edges → false confidence in blast radius | **Ours (the honesty half).** The CLI now labels every blast radius as *recorded* edges and says so explicitly when only scanner-visible edges exist. Discovering the invisible edges is layer-2→3 flow: minds find them, `link` records them, the gate keeps them. |
| File-grained, misses signature-level breakage | **Layer 4's job.** Use types and tests; the graph tells you *which* neighbors to point them at. |
| Doesn't remember decisions or failed attempts | **Layer 2's job.** Pair GraphCoding with any episodic store; point summaries at it when the why matters. |
| Decays if nobody writes intent | **Ours to measure, yours to spend.** The gate holds the floor mechanically; `health` makes the upper floors' decay visible and specific. No tool can force a team to care — it can only make not-caring impossible to miss. |

## Minimal complete stack, concretely

For a solo dev or a small agent fleet, the whole four-layer architecture is already lying around:

1. **Retrieval:** your editor's search + (optionally) an embeddings sidecar ([scaling](scaling.md)).
2. **Episodic:** a `decisions.md` / memory directory / MCP memory server — anything append-friendly the agent reads at session start.
3. **Design-state:** `graphcoding init --hooks`, the [loop](lifecycle.md), CI gate.
4. **Verification:** the type checker and test runner you already have, kept honest by CI.

Agents get all four wired in one paragraph of system prompt: *retrieve to find, read episodic for the why, query the graph before touching, plan into the graph before building, and no done-claims until tests pass and drift is NONE.*

That's the whole architecture. Four small disciplines instead of one mythical "memory" — and the piece that was missing now has a gate on it.
