# Contributing

Issues and PRs welcome. This project eats its own cooking, so the workflow is the methodology:

## The rule

**Every PR's graph diff must tell the story of the change before the code diff does.**

1. `graphcoding show` whatever you're about to touch (know the blast radius).
2. New files → `graphcoding plan` them first, with a real one-line summary.
3. Removals → `graphcoding mark-delete` first.
4. `graphcoding sync --staged` before each commit; include `.graphcoding/graph.jsonl`.
5. CI runs the test suite and an unscoped `graphcoding drift` — both must pass.

## What's most wanted

- **Language scanners.** One function per language in `src/graphcoding/scan.py`
  (imports extraction + summary seeding). Go, Rust, Java, Ruby, PHP, Terraform, SQL —
  each is a well-contained PR with obvious tests.
- **Embeddings sidecar** (rung 1 of [docs/scaling.md](docs/scaling.md)) as an
  optional extra — semantic `query` without breaking zero-dependency core.
- **Harness integrations.** Rules/skill files for agent harnesses we don't cover yet.
- **Migration war stories.** Adopted GraphCoding on a real repo? A short writeup
  of what worked and what fought you is worth more than code.

## Ground rules

- Core stays **zero-dependency** (Python stdlib only). Optional extras may depend on things.
- The graph file format is a compatibility surface — changes to it need an issue first.
- Tests: `pytest tests/ -q`. New behavior needs a test that fails without it.

## Dev setup

```bash
git clone https://github.com/mosabsayyed/graphcoding
cd graphcoding
pip install -e . pytest
pytest tests/ -q
graphcoding status   # meet the repo through its own graph
```
