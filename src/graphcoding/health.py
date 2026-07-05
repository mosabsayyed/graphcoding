"""Memory-quality report — the decay counter.

The drift gate holds the floor (structure can't rot). This module measures the
upper floors, which CAN rot: summaries, intent edges, lifecycle hygiene.
`graphcoding health` names what's decaying so neglect is visible long before
it hurts. Informational — always exits 0; quality is steered, not gated.

Checks:
  * summary coverage        nodes with no summary at all
  * stale-summary suspects  stored summary no longer matches what the file's
                            own docstring/first-comment says (computed live —
                            nothing extra is stored, so no graph-diff noise)
  * needs-analysis backlog  machine-guessed summaries awaiting a mind
  * orphans                 nodes with no edges either way — unmapped territory
  * intent-edge richness    hand-recorded CALLS/REFERENCES/DEPENDS_ON count;
                            the graph's irreplaceable layer
"""
from __future__ import annotations

from .scan import scan_file
from .store import Graph

INTENT_EDGES = ("CALLS", "REFERENCES", "DEPENDS_ON", "RELATED_TO",
                "INHERITS", "IMPLEMENTS")


def compute_health(root: str, cfg: dict, graph: Graph) -> dict:
    files = graph.file_nodes()
    incoming_counts: dict[str, int] = {}
    for n in graph.nodes.values():
        for e in n.edges:
            incoming_counts[e["to"]] = incoming_counts.get(e["to"], 0) + 1

    no_summary, stale_suspects, needs_analysis, orphans = [], [], [], []
    intent_edges = 0
    for path, node in sorted(files.items()):
        if node.status == "planned":
            continue
        if not node.summary:
            no_summary.append(path)
        else:
            # live re-extraction; a differing fresh auto-summary means the
            # file's self-description moved while the stored summary didn't
            fresh, _ = scan_file(root, path, {**cfg, "scan_symbols": False})
            if fresh.summary and fresh.summary != node.summary \
                    and len(fresh.summary) >= len(node.summary):
                stale_suspects.append((path, node.summary, fresh.summary))
        if node.status == "needs-analysis":
            needs_analysis.append(path)
        if not node.edges and not incoming_counts.get(path):
            orphans.append(path)
        intent_edges += sum(1 for e in node.edges if e["type"] in INTENT_EDGES)

    total = len([n for n in files.values() if n.status != "planned"])
    return {
        "total": total,
        "no_summary": no_summary,
        "stale_suspects": stale_suspects,
        "needs_analysis": needs_analysis,
        "orphans": orphans,
        "intent_edges": intent_edges,
    }


def format_health(h: dict) -> str:
    total = max(h["total"], 1)
    covered = h["total"] - len(h["no_summary"])
    out = ["=== graphcoding health — memory quality ==="]
    out.append(f"nodes: {h['total']}   summary coverage: {covered}/{h['total']} "
               f"({100 * covered // total}%)   hand-recorded intent edges: {h['intent_edges']}")

    def block(title: str, items: list, render) -> None:
        if not items:
            return
        out.append(f"\n{title} ({len(items)}):")
        for it in items[:15]:
            out.append(render(it))
        if len(items) > 15:
            out.append(f"   … and {len(items) - 15} more")

    block("no summary — invisible to query and to agents", h["no_summary"],
          lambda p: f"   · {p}")
    block("stale-summary suspects — file's self-description moved, graph didn't",
          h["stale_suspects"],
          lambda s: f"   ~ {s[0]}\n     graph: {s[1][:70]}\n     file:  {s[2][:70]}")
    block("needs-analysis — machine guesses awaiting a mind", h["needs_analysis"],
          lambda p: f"   ? {p}")
    block("orphans — no edges either way; unmapped or genuinely dead",
          h["orphans"], lambda p: f"   ø {p}")

    if h["intent_edges"] == 0 and h["total"] > 5:
        out.append("\nzero hand-recorded edges: the graph is still only a scan. "
                   "Record what no scanner sees (HTTP calls, queues, cron→table): "
                   "graphcoding link <src> CALLS <dst>")
    if not (h["no_summary"] or h["stale_suspects"] or h["needs_analysis"]):
        out.append("\nmemory is healthy: every node carries current, human-grade intent.")
    return "\n".join(out)
