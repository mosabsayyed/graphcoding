# Drift — detection and enforcement

Drift is any disagreement between the working tree and the graph. GraphCoding's core claim — *the graph can be trusted* — holds only because drift is detected mechanically and blocked at the commit boundary.

## The five findings

`graphcoding drift` compares every tracked file on disk against every file-level node:

| Finding | Disk | Graph | Blocking | Fix |
|---|---|---|---|---|
| `missing_node` | file exists | no node | **yes** | `graphcoding sync` |
| `ghost_node` | file gone | node remains | **yes** | `graphcoding sync` |
| `built_not_synced` | file exists | still `planned` | **yes** | `graphcoding sync` |
| `not_deleted` | file exists | `to-be-deleted` | **yes** | delete the file (or revert the mark), then sync |
| `unbuilt_planned` | no file | `planned` | no | build it — this *is* the plan |

Exit code: `1` if any blocking finding, `0` otherwise. Pipe-friendly, CI-friendly.

Note the asymmetry in the fix column: three findings are auto-repairable because the *code* is the truth (sync makes the graph follow). `not_deleted` is not auto-repaired — the *graph* is the truth there (a decision was recorded), and silently un-deciding it would defeat the point. The tool surfaces it and a human/agent finishes the deletion or reverts the decision explicitly.

## Scoping: `--staged`

```bash
graphcoding drift            # whole tree — the honest global answer
graphcoding drift --staged   # only files staged for commit — the fair local gate
```

The full report and the gate answer different questions. On a shared checkout or busy team, the whole tree often drifts because of *someone else's* work-in-progress. Gating your commit on their mess would deadlock everyone. So:

- **pre-commit hook** runs `--staged`: your commit is blocked only if a file *you are committing* is out of sync. Exit 0 when nothing relevant is staged.
- **CI** runs unscoped: the merge is blocked if *anything* drifts. The main branch is always globally clean.

This split is what makes the gate socially survivable. A gate that blocks people for others' sins gets `--no-verify`'d into oblivion within a week.

## The three enforcement layers

```
you edit ──► git commit ──► pre-commit: drift --staged ──► blocked? sync, retry
                    │
                    └─► post-commit: sync --commit HEAD    (auto-repair net)
                                │
                                └─► push ──► CI: drift     (required check)
```

1. **pre-commit** (installed by `graphcoding hooks` or `init --hooks`) — catches drift when it is cheapest: before it enters history, scoped to the author's own files.
2. **post-commit** — best-effort auto-sync of whatever was just committed. Catches merges, cherry-picks, and the occasional `--no-verify`. Note it syncs the graph *file* in the working tree; the follow-up commit picks it up (or the pre-commit gate of the next commit forces it).
3. **CI** (see [templates/github-action-drift.yml](../templates/github-action-drift.yml)) — the arbiter. Unscoped drift check as a required status. Nothing stale merges, no matter what happened on laptops.

## Recovering from drift

Small drift (the daily case):

```bash
graphcoding sync        # no args: repairs every auto-repairable finding
graphcoding drift       # must print DRIFT=NONE
```

Large drift (you turned the gate off for a month; a vendored tree landed; a big branch merged badly):

```bash
graphcoding scan        # full re-sweep: adds missing, refreshes stale
graphcoding drift       # ghosts remain? sync removes them
graphcoding sync && graphcoding drift
```

**Reconcile incrementally; never rebuild from a snapshot.** `scan` and `sync` upsert — they preserve every human-written summary, every planned node, every hand-recorded edge. Deleting the graph and re-scanning "to be safe" destroys exactly the layer that can't be regenerated (intent and cross-boundary edges) to refresh the layer that regenerates itself anyway (imports). There is no situation where that trade is right.

## What drift detection deliberately doesn't check

- **Edge freshness.** A file can change its imports without changing its node set; import edges refresh on the next `sync` of that file (which the hooks guarantee happens at the commit touching it). Between syncs, edges for *unchanged* files are exact; that's what bounds the error.
- **Summary truthfulness.** No tool can verify that "handles refunds" still describes the code. The mitigation is social + mechanical: summaries refresh from docstrings on every sync, and the QUERY discipline means wrong summaries get noticed by the next reader — who fixes one line.
- **Semantic drift** (code does something subtly different than intended). That's what tests are for. GraphCoding gates *structural and intent* drift; it complements a test suite, never replaces it.
