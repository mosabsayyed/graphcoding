# FAQ — the fair objections

### "Isn't this just documentation with extra steps?"

Documentation *describes* and nothing happens when it's wrong. The graph *constrains*: when it disagrees with the code, **commits stop** until they agree again. That single property — enforcement at the commit boundary — is the difference between this and every architecture wiki you've watched rot. Also unlike docs, half the graph (nodes, import edges) maintains itself by scanning.

### "My IDE / language server already knows the call graph."

For one language, one process boundary, while it's running, for you only. The graph adds what the LSP can't hold: **cross-boundary edges** (HTTP, queues, cron→table — no static analyzer sees these), **intent** (summaries, *planned*, *to-be-deleted* — dimensions code doesn't have), **persistence in version control** (branchable, reviewable, diffable), and **availability to agents and CI** that don't run your IDE. Use both; they answer different questions.

### "Won't the graph just rot like every other artifact?"

The regenerable layer (files, imports) mechanically can't rot — the gate blocks commits that would desync it, and `sync` rebuilds it from source anytime. The intent layer (summaries, cross-boundary edges) can *age*, but it degrades gracefully: a stale summary is one line, gets read often (QUERY is step 1 of everything), and costs seconds to fix at the moment it's noticed. Compare a stale design doc: read never, trusted blindly when finally found, cost of a rewrite nobody does.

### "This is overhead. I just want to code."

Count the overhead honestly: `show` before an edit (seconds, and it replaces the grep-and-scroll you were doing anyway, with better answers), one `plan` line per new file (you were deciding what the file was for regardless — now it's written down), `sync --staged` per commit (automatic via hook). Against: one production incident from an unseen caller, one afternoon reconstructing why a module exists, one agent session re-learning your codebase wrong. The loop is the cheapest insurance in the building.

If you truly want zero ceremony: `init --hooks` and never run `plan` at all. You still get blast radius, current summaries, drift-proof structure — scan + sync + gate do that alone. Design-first is the upper floor, not the entry fee.

### "We have 400k files. Will this hold?"

Rung 0 (JSONL + token search) is comfortable to ~50k nodes (see [scaling](scaling.md)). Past that: per-subtree graphs, or the database mirror. But check the premise — you gate per-repo, and very few single repos that humans/agents actively edit exceed tens of thousands of *tracked source* files once generated code is ignored.

### "What about files the scanner doesn't understand — Go, Rust, Terraform, SQL?"

They get file nodes with language + seed summary; you add the edges that matter by hand (`link`). That sounds worse than it is: the methodology's value concentrates in summaries, statuses, and cross-boundary edges — which are manual in *every* language. Import auto-extraction for more languages is the most welcome kind of PR (one regex/parser function per language in `scan.py`).

### "Two people edited the graph and it conflicted."

Sorted line-per-node JSONL makes conflicts rare (different nodes = different lines) and dumb when they happen (keep both lines, run `graphcoding drift`). A conflict on the *same* node means two people redefined the same thing simultaneously — that's not a file-format problem; that's the file format catching a real coordination problem at the cheapest possible moment.

### "Can I lie to it? Just sync whatever I wrote?"

Yes — `sync` after freestyle coding produces a truthful *structural* graph with no design step. That's rung-zero usage and it's fine (see overhead question). What you can't do is *silently* diverge: the file you didn't plan still shows up in the graph diff of your PR, named, for your reviewer to ask about. The system's floor is honesty, not virtue.

### "How is this different from [architecture-as-code tool / C4 / dependency-cruiser]?"

Those render or validate **descriptions written beside the system**. GraphCoding maintains a model **generated from and gating the system itself**, at file granularity, carrying lifecycle state (*planned/doomed*), inside version control, queryable by agents mid-task. Closest cousins are dependency-graph linters — which cover exactly the layer here that's automated (imports) and none of the layer that's the point (intent, lifecycle, cross-boundary).

### "Why should the graph live in git instead of a proper database?"

Because truth needs the same lifecycle as code: branch, review, revert, blame, merge. A database has none of those; it has *state*. Databases make great mirrors ([scaling](scaling.md), rung 2) and terrible sources of truth for something that must move in lockstep with commits. The day your graph's history matters — "when did we decide this module was doomed, and who approved it?" — git answers in one command.

### "Does this replace tests / types / code review?"

No — it completes them. Types verify what code *is* within a compiler's horizon. Tests verify what code *does* at the points you thought to check. Review verifies what a human noticed. GraphCoding verifies the layer all three assume and none check: that the system's *structure and intent* match what's on disk, across every boundary, including the parts that should exist but don't yet and the parts that exist but shouldn't.
