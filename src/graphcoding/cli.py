"""graphcoding — the CLI.

Commands map 1:1 to the GraphCoding loop:

  QUERY    query, show, status
  DESIGN   plan, link, mark-delete
  CODE     (your editor / your agent)
  SYNC     sync
  VERIFY   drift

Plus lifecycle: init, scan, hooks.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from . import __version__
from .drift import blocking_count, compute_drift, format_report
from .scan import scan_repo, trackable
from .store import (DEFAULT_CONFIG, EDGE_TYPES, GRAPH_DIR, NODE_TYPES, Graph,
                    Node, config_path, find_root, load_config)
from .sync import sync as run_sync
from . import hooks as hooks_mod


def _root_or_die(args) -> str:
    root = find_root(getattr(args, "root", None))
    if not root:
        sys.exit("no .graphcoding/ found — run `graphcoding init` at your repo root")
    return root


def _print_node(g: Graph, node: Node, verbose: bool = True) -> None:
    print(f"{node.name}")
    print(f"  type: {node.type}   status: {node.status}"
          + (f"   language: {node.language}" if node.language else ""))
    if node.summary:
        print(f"  summary: {node.summary}")
    if verbose:
        outgoing = sorted(node.edges, key=lambda e: (e["type"], e["to"]))
        if outgoing:
            print("  outgoing:")
            for e in outgoing:
                missing = "" if e["to"] in g.nodes else "   (planned/missing)"
                print(f"    -[{e['type']}]-> {e['to']}{missing}")
        incoming = g.incoming(node.name)
        if incoming:
            print("  recorded incoming edges (blast radius — these break if you change it):")
            for src, etype in incoming:
                print(f"    <-[{etype}]- {src}")
            if all(etype in ("IMPORTS", "CONTAINS") for _, etype in incoming):
                print("    (scanner-visible edges only; runtime/cross-boundary callers"
                      " may exist unrecorded — record with: graphcoding link <src> CALLS"
                      f" {node.name})")
        elif not node.name.endswith((".md", ".json")):
            print("  recorded incoming edges: none — likely safe to change, but the"
                  " graph only knows recorded edges; verify runtime refs once, then"
                  " record them")


# ---------------------------------------------------------------- commands --
def cmd_init(args) -> None:
    root = os.path.abspath(args.root or os.getcwd())
    gdir = os.path.join(root, GRAPH_DIR)
    os.makedirs(gdir, exist_ok=True)
    cfgp = config_path(root)
    if not os.path.exists(cfgp):
        with open(cfgp, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
            f.write("\n")
    g = Graph.load(root)
    g.save()
    print(f"initialized {os.path.relpath(gdir, os.getcwd())}/ (config.json + graph.jsonl)")
    if not args.no_scan:
        cfg = load_config(root)
        stats = scan_repo(root, cfg, g)
        g.save()
        print(f"scanned: {stats['files']} files -> {stats['added']} nodes added, "
              f"{stats['updated']} updated")
    if args.hooks:
        for p in hooks_mod.install(root):
            print(f"installed hook: {os.path.relpath(p, root)}")
    print("next: `graphcoding status` · commit .graphcoding/ with your code")


def cmd_scan(args) -> None:
    root = _root_or_die(args)
    cfg = load_config(root)
    g = Graph.load(root)
    stats = scan_repo(root, cfg, g)
    g.save()
    print(f"scanned {stats['files']} files: {stats['added']} added, "
          f"{stats['updated']} updated — graph now {len(g.nodes)} nodes")


def cmd_plan(args) -> None:
    root = _root_or_die(args)
    g = Graph.load(root)
    node = Node(name=args.name, type=args.type, status="planned",
                summary=args.summary or "")
    for spec in args.edge or []:
        try:
            etype, target = spec.split(":", 1)
        except ValueError:
            sys.exit(f"bad --edge '{spec}' (want TYPE:target, e.g. IMPORTS:src/db.py)")
        etype = etype.upper()
        if etype not in EDGE_TYPES:
            sys.exit(f"unknown edge type {etype} (one of {', '.join(EDGE_TYPES)})")
        node.add_edge(target, etype)
    existing = g.nodes.get(args.name)
    if existing and existing.status != "planned" and not args.force:
        sys.exit(f"{args.name} already exists with status={existing.status}; "
                 "use --force to re-plan it")
    if existing:
        existing.status = "planned"
        if args.summary:
            existing.summary = args.summary
        for e in node.edges:
            existing.add_edge(e["to"], e["type"])
    else:
        g.nodes[node.name] = node
    g.save()
    print(f"planned: {args.name}" + (f" — {args.summary}" if args.summary else ""))


def cmd_link(args) -> None:
    root = _root_or_die(args)
    g = Graph.load(root)
    src = g.nodes.get(args.source)
    if not src:
        sys.exit(f"unknown source node {args.source} (plan or scan it first)")
    etype = args.type.upper()
    if etype not in EDGE_TYPES:
        sys.exit(f"unknown edge type {etype} (one of {', '.join(EDGE_TYPES)})")
    added = src.add_edge(args.target, etype)
    g.save()
    note = "" if args.target in g.nodes else "  (target not in graph yet — planned work)"
    print(("linked" if added else "already linked")
          + f": {args.source} -[{etype}]-> {args.target}{note}")


def cmd_mark_delete(args) -> None:
    root = _root_or_die(args)
    g = Graph.load(root)
    node = g.nodes.get(args.name)
    if not node:
        sys.exit(f"unknown node {args.name}")
    incoming = g.incoming(args.name)
    if incoming and not args.force:
        print(f"{args.name} has {len(incoming)} incoming edge(s):")
        for s, t in incoming:
            print(f"  <-[{t}]- {s}")
        sys.exit("refusing to mark for deletion — update the callers first, "
                 "or pass --force if they are part of the same removal")
    node.status = "to-be-deleted"
    g.save()
    print(f"marked to-be-deleted: {args.name} "
          "(delete the file, then `graphcoding sync`)")


def cmd_sync(args) -> None:
    root = _root_or_die(args)
    cfg = load_config(root)
    g = Graph.load(root)
    res = run_sync(root, cfg, g, staged=args.staged, commit=args.commit,
                   files=args.files)
    if not args.quiet:
        print(f"sync: {len(res['upserted'])} upserted, {len(res['removed'])} removed")
        for p in res["upserted"][:15]:
            print(f"   ~ {p}")
        for p in res["removed"][:15]:
            print(f"   - {p}")
        for p in res["skipped"]:
            print(f"   ! {p} marked deleted in git but still on disk — skipped")
        planned = g.with_status("planned")
        if planned:
            print(f"still planned: {len(planned)} node(s) — `graphcoding status`")


def cmd_drift(args) -> None:
    root = _root_or_die(args)
    cfg = load_config(root)
    g = Graph.load(root)
    report = compute_drift(root, cfg, g)
    scope = None
    if args.staged:
        try:
            out = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only"],
                                 capture_output=True, text=True, check=True).stdout
            scope = {p for p in out.splitlines() if p.strip() and trackable(p, cfg)}
        except (subprocess.CalledProcessError, FileNotFoundError):
            scope = set()
        if not scope:
            sys.exit(0)  # nothing staged that we track
    n = blocking_count(report, scope)
    if not (args.quiet and n == 0):
        print(format_report(report, scope))
    sys.exit(1 if n else 0)


def cmd_status(args) -> None:
    root = _root_or_die(args)
    cfg = load_config(root)
    g = Graph.load(root)
    by_status: dict[str, int] = {}
    for n in g.nodes.values():
        by_status[n.status] = by_status.get(n.status, 0) + 1
    edges = sum(len(n.edges) for n in g.nodes.values())
    print(f"graph: {len(g.nodes)} nodes, {edges} edges "
          f"({', '.join(f'{k}={v}' for k, v in sorted(by_status.items()))})")
    planned = g.with_status("planned")
    if planned:
        print(f"\nplanned — left to build ({len(planned)}):")
        for n in planned:
            print(f"   ? {n.name}" + (f" — {n.summary}" if n.summary else ""))
    doomed = g.with_status("to-be-deleted")
    if doomed:
        print(f"\nto-be-deleted — left to remove ({len(doomed)}):")
        for n in doomed:
            print(f"   ! {n.name}")
    broken = []
    for n in g.nodes.values():
        for e in n.edges:
            if e["to"] not in g.nodes:
                broken.append((n.name, e["type"], e["to"]))
    if broken:
        print(f"\ndangling edges — dependencies not wired yet ({len(broken)}):")
        for s, t, d in sorted(broken)[:20]:
            print(f"   {s} -[{t}]-> {d}")
    rep = compute_drift(root, cfg, g)
    n_block = blocking_count(rep)
    print(f"\ndrift: {'NONE' if not n_block else f'{n_block} blocking — run `graphcoding drift`'}")


def cmd_summary(args) -> None:
    root = _root_or_die(args)
    g = Graph.load(root)
    node = g.nodes.get(args.name)
    if not node:
        sys.exit(f"unknown node {args.name} (scan or plan it first)")
    node.summary = args.text
    if node.status == "needs-analysis":
        node.status = "ok"
    g.save()
    print(f"summary set: {args.name} — {args.text}")


def cmd_health(args) -> None:
    from .health import compute_health, format_health
    root = _root_or_die(args)
    cfg = load_config(root)
    g = Graph.load(root)
    print(format_health(compute_health(root, cfg, g)))


def cmd_query(args) -> None:
    root = _root_or_die(args)
    g = Graph.load(root)
    results = g.search(args.terms, limit=args.limit)
    if not results:
        print("no matches")
        return
    for score, node in results:
        line = f"{node.name}  [{node.type}/{node.status}]"
        if node.summary:
            line += f" — {node.summary}"
        print(line)


def cmd_show(args) -> None:
    root = _root_or_die(args)
    g = Graph.load(root)
    node = g.nodes.get(args.name)
    if not node:
        hits = g.search([args.name], limit=5)
        if len(hits) == 1:
            node = hits[0][1]
        elif hits:
            print(f"no exact node '{args.name}'; close matches:")
            for _, n in hits:
                print(f"   {n.name}")
            sys.exit(1)
        else:
            sys.exit(f"no node named or matching '{args.name}'")
    _print_node(g, node)


def cmd_hooks(args) -> None:
    root = _root_or_die(args)
    for p in hooks_mod.install(root):
        print(f"installed: {os.path.relpath(p, root)}")


# ------------------------------------------------------------------ parser --
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="graphcoding",
        description="GraphCoding — your repo's living knowledge graph. "
                    "Query before you touch code; the graph is the design contract.")
    p.add_argument("--version", action="version", version=f"graphcoding {__version__}")
    p.add_argument("--root", help="repo root (default: walk up from cwd)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="create .graphcoding/ and scan the repo")
    s.add_argument("--no-scan", action="store_true", help="skip the initial scan")
    s.add_argument("--hooks", action="store_true", help="also install git hooks")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("scan", help="(re)scan the whole repo into the graph")
    s.set_defaults(func=cmd_scan)

    s = sub.add_parser("plan", help="declare a node you intend to build (DESIGN)")
    s.add_argument("name", help="repo-relative path, or path::Symbol")
    s.add_argument("--summary", "-s", help="one line: what it will do")
    s.add_argument("--type", "-t", default="CodeFile", choices=NODE_TYPES)
    s.add_argument("--edge", "-e", action="append",
                   help="TYPE:target (repeatable), e.g. -e IMPORTS:src/db.py")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_plan)

    s = sub.add_parser("link", help="add an edge between nodes")
    s.add_argument("source")
    s.add_argument("type", help="|".join(EDGE_TYPES))
    s.add_argument("target")
    s.set_defaults(func=cmd_link)

    s = sub.add_parser("mark-delete", help="mark a node's file for removal")
    s.add_argument("name")
    s.add_argument("--force", action="store_true",
                   help="mark even with incoming edges")
    s.set_defaults(func=cmd_mark_delete)

    s = sub.add_parser("sync", help="reconcile the graph with changed files (SYNC)")
    s.add_argument("--staged", action="store_true", help="sync staged changes")
    s.add_argument("--commit", nargs="?", const="HEAD",
                   help="sync files changed in a commit (default HEAD)")
    s.add_argument("--files", nargs="*", help="sync explicit files")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("drift", help="working tree vs graph; exit 1 on drift (VERIFY)")
    s.add_argument("--staged", action="store_true",
                   help="only gate on files staged for commit")
    s.add_argument("--quiet", action="store_true", help="print nothing when clean")
    s.set_defaults(func=cmd_drift)

    s = sub.add_parser("status", help="planned work, dangling edges, drift summary")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("health", help="memory quality: coverage, stale summaries, orphans")
    s.set_defaults(func=cmd_health)

    s = sub.add_parser("summary", help="set/replace a node's one-line intent")
    s.add_argument("name")
    s.add_argument("text")
    s.set_defaults(func=cmd_summary)

    s = sub.add_parser("query", help="search nodes by name + summary (QUERY)")
    s.add_argument("terms", nargs="+")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_query)

    s = sub.add_parser("show", help="one node: summary, edges, blast radius (QUERY)")
    s.add_argument("name")
    s.set_defaults(func=cmd_show)

    s = sub.add_parser("hooks", help="install pre-commit gate + post-commit sync")
    s.set_defaults(func=cmd_hooks)
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
