# Starting a new project graph-first

Greenfield is where GraphCoding is purest: the graph exists **before the code**, so the first commit of the project is its architecture — reviewable, versioned, and enforceable from line one.

## The ritual

```bash
mkdir myapp && cd myapp && git init -b main
graphcoding init --hooks          # empty graph + gate, before any code exists
```

Now hold the architecture session in `plan` commands instead of a whiteboard photo:

```bash
graphcoding plan src/main.py      -s "Entry point: config, db, http wiring — no logic"
graphcoding plan src/config.py    -s "All env/settings reads; nothing else touches os.environ"
graphcoding plan src/db/core.py   -s "Engine + session factory; the only module that knows the DSN"
graphcoding plan src/db/models.py -s "SQLAlchemy models" -e IMPORTS:src/db/core.py

graphcoding plan src/services/accounts.py \
  -s "Account lifecycle: signup, verify, close. Owns the Account invariants" \
  -e IMPORTS:src/db/models.py

graphcoding plan src/api/accounts.py \
  -s "HTTP layer over accounts service; validation + status codes only" \
  -e IMPORTS:src/services/accounts.py

git add .graphcoding && git commit -m "design: v0 architecture"
```

Notice what those summaries are doing: each one states a **responsibility boundary** ("the only module that…", "…only", "owns the…"). At design time this costs one clause; discovered later it costs an archaeology session. The graph is the cheapest moment you will ever have to write these down.

## Build to the graph

```bash
graphcoding status
# planned — left to build (6): ...
```

Work the list. Each commit: build a node or two, `sync --staged` (or let the hook remind you), commit. The project's history reads as *design → fulfillment*, and at any moment `status` shows exactly how much architecture is still promissory.

Discover mid-build that the design was wrong? Change the design **in the graph first** — re-`plan`, re-`link`, delete the planned node — then code. It's one command either way, and the correction is now part of the record instead of a silent divergence.

## Why bother when the repo is three files

Because the payoff compounds from day one:

- **Day 1:** the design session produces an artifact instead of a memory.
- **Week 2:** the first "wait, should parsing live in the service or the route?" is answered by reading two summaries, not by taste-of-the-day.
- **Month 2:** an agent (or a collaborator) joins; their entire onboarding is `graphcoding status` + `query`. They inherit the responsibility boundaries you wrote when the system was small enough to state them.
- **Month 6:** the repo is 400 files and *never had a moment* where the graph and code diverged — because the gate was on before file one. Retrofitting this property later is possible (see [migration](migrating-existing-repos.md)) but strictly worse.

## Greenfield with an agent doing the building

The cleanest division of labor GraphCoding enables:

1. **You** (or you + agent, brainstorming) hold the design session → `plan` commands → design commit.
2. **Agent** gets one instruction: *"Run `graphcoding status`. Build until it's clean. Query before touching anything. You may not create files that aren't planned — if you believe one is needed, plan it with a summary and say why."*
3. **You review** twice, at the right altitude each time: the design diff (shape, small, high-leverage) and the build diff (code, mechanical to check against the already-approved shape).

The agent can't wander — unplanned files are drift with its name on them. Sessions can die and restart freely — `status` reconstructs the exact work state from the repo itself. And the "why" of every module survives in summaries that were written when the design intent was freshest.

## Template

`templates/` in this repo carries the pieces a new project wants on day one:

- `CLAUDE.md.snippet` / `cursorrules.snippet` — the agent contract
- `github-action-drift.yml` — CI gate
- the [skill](../skill/graphcoding/SKILL.md) for skill-aware harnesses

Copy them in during `init`, and the project is agent-ready before it has code.
