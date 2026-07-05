"""End-to-end tests: the full GraphCoding loop on a throwaway git repo.

Covers: init/scan (migration), plan (design), drift gate (verify),
sync (build + delete), blast radius, status, search, hook install.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from graphcoding.cli import main  # noqa: E402
from graphcoding.store import Graph  # noqa: E402


def run(repo, *argv, expect_exit=None):
    """Invoke the CLI in-process; return SystemExit code (0 if none)."""
    old = os.getcwd()
    os.chdir(repo)
    try:
        try:
            main(list(argv))
            code = 0
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        os.chdir(old)
    if expect_exit is not None:
        assert code == expect_exit, f"{argv} exited {code}, wanted {expect_exit}"
    return code


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = str(tmp_path)
    git(r, "init", "-b", "main")
    git(r, "config", "user.email", "t@t.t")
    git(r, "config", "user.name", "t")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(
        '"""App entry point."""\nfrom src import db\n\ndef run():\n    return db.get()\n')
    (tmp_path / "src" / "db.py").write_text(
        '"""Database layer."""\n\ndef get():\n    return 1\n')
    (tmp_path / "src" / "util.js").write_text(
        "// String helpers for the UI\nimport { x } from './helpers'\n")
    (tmp_path / "src" / "helpers.js").write_text("// misc helpers\nexport const x = 1\n")
    git(r, "add", "-A")
    git(r, "commit", "-m", "seed")
    return r


def test_init_scans_existing_repo(repo, capsys):
    run(repo, "init", expect_exit=0)
    g = Graph.load(repo)
    assert "src/app.py" in g.nodes
    assert g.nodes["src/app.py"].summary == "App entry point."
    assert {"to": "src/db.py", "type": "IMPORTS"} in g.nodes["src/app.py"].edges
    assert {"to": "src/helpers.js", "type": "IMPORTS"} in g.nodes["src/util.js"].edges
    run(repo, "drift", expect_exit=0)  # freshly scanned = no drift


def test_blast_radius(repo, capsys):
    run(repo, "init")
    capsys.readouterr()
    run(repo, "show", "src/db.py", expect_exit=0)
    out = capsys.readouterr().out
    assert "blast radius" in out and "src/app.py" in out


def test_missing_node_is_drift_and_sync_fixes_it(repo, capsys):
    run(repo, "init")
    with open(os.path.join(repo, "src", "new.py"), "w") as f:
        f.write('"""Brand new module."""\n')
    git(repo, "add", "-A")
    run(repo, "drift", expect_exit=1)
    out = capsys.readouterr().out
    assert "missing_node: 1" in out and "src/new.py" in out
    run(repo, "sync", expect_exit=0)
    run(repo, "drift", expect_exit=0)
    g = Graph.load(repo)
    assert g.nodes["src/new.py"].summary == "Brand new module."


def test_plan_then_build_then_sync(repo, capsys):
    run(repo, "init")
    run(repo, "plan", "src/api.py", "-s", "HTTP layer over db",
        "-e", "IMPORTS:src/db.py", expect_exit=0)
    g = Graph.load(repo)
    assert g.nodes["src/api.py"].status == "planned"
    run(repo, "drift", expect_exit=0)  # unbuilt planned is informational
    capsys.readouterr()
    run(repo, "status")
    assert "src/api.py" in capsys.readouterr().out
    # build it, but "forget" to sync: planned + on disk = blocking drift
    with open(os.path.join(repo, "src", "api.py"), "w") as f:
        f.write('"""HTTP layer."""\nfrom src import db\n')
    git(repo, "add", "-A")
    run(repo, "drift", expect_exit=1)
    run(repo, "sync", "--staged", expect_exit=0)
    g = Graph.load(repo)
    assert g.nodes["src/api.py"].status == "ok"
    # the richer design-intent summary survives the shorter docstring
    assert g.nodes["src/api.py"].summary == "HTTP layer over db"
    run(repo, "drift", expect_exit=0)


def test_delete_lifecycle(repo, capsys):
    run(repo, "init")
    # refuses while there are callers
    run(repo, "mark-delete", "src/db.py", expect_exit=1)
    # helpers.js has an incoming edge from util.js too; delete util first
    run(repo, "mark-delete", "src/util.js", expect_exit=0)
    run(repo, "drift", expect_exit=1)  # marked but still on disk = not_deleted
    os.remove(os.path.join(repo, "src", "util.js"))
    git(repo, "add", "-A")
    run(repo, "sync", expect_exit=0)
    g = Graph.load(repo)
    assert "src/util.js" not in g.nodes
    assert g.incoming("src/helpers.js") == []  # edge cleaned up
    run(repo, "drift", expect_exit=0)


def test_ghost_node_detected(repo, capsys):
    run(repo, "init")
    os.remove(os.path.join(repo, "src", "helpers.js"))
    # also drop the edge holder so only the ghost remains blocking… keep it:
    run(repo, "drift", expect_exit=1)
    out = capsys.readouterr().out
    assert "ghost_node" in out and "src/helpers.js" in out


def test_query(repo, capsys):
    run(repo, "init")
    capsys.readouterr()
    run(repo, "query", "database", expect_exit=0)
    assert "src/db.py" in capsys.readouterr().out


def test_staged_scope_ignores_others_wip(repo, capsys):
    """Teammate WIP (untracked-in-graph file, unstaged) must not block my commit."""
    run(repo, "init")
    with open(os.path.join(repo, "src", "teammate_wip.py"), "w") as f:
        f.write("x = 1\n")
    with open(os.path.join(repo, "src", "mine.py"), "w") as f:
        f.write('"""Mine."""\n')
    git(repo, "add", "src/mine.py")
    run(repo, "drift", "--staged", expect_exit=1)   # my staged file drifts
    run(repo, "sync", "--staged")
    run(repo, "drift", "--staged", expect_exit=0)   # teammate's file ignored
    run(repo, "drift", expect_exit=1)               # full report still honest


def test_hooks_install_and_gate(repo, capsys):
    run(repo, "init")
    run(repo, "hooks", expect_exit=0)
    pre = os.path.join(repo, ".git", "hooks", "pre-commit")
    assert os.path.exists(pre) and os.access(pre, os.X_OK)
    assert "graphcoding drift --staged" in open(pre).read()


def test_health_reports_quality(repo, capsys):
    run(repo, "init")
    # a file with no docstring at all -> no summary
    with open(os.path.join(repo, "src", "bare.py"), "w") as f:
        f.write("x = 1\n")
    run(repo, "sync", "--files", "src/bare.py")
    capsys.readouterr()
    run(repo, "health", expect_exit=0)
    out = capsys.readouterr().out
    assert "no summary" in out and "src/bare.py" in out
    # stale suspect: docstring moves on, stored summary doesn't
    g = Graph.load(repo)
    g.nodes["src/db.py"].summary = "Old description nobody updated"
    g.save()
    with open(os.path.join(repo, "src", "db.py"), "w") as f:
        f.write('"""Totally rewritten storage engine."""\n\ndef get():\n    return 2\n')
    run(repo, "health", expect_exit=0)
    out = capsys.readouterr().out
    assert "stale-summary suspects" in out and "src/db.py" in out


def test_summary_command(repo, capsys):
    run(repo, "init")
    run(repo, "summary", "src/db.py", "The only module that owns the connection")
    g = Graph.load(repo)
    assert g.nodes["src/db.py"].summary == "The only module that owns the connection"


def test_show_discloses_recorded_only(repo, capsys):
    run(repo, "init")
    capsys.readouterr()
    run(repo, "show", "src/db.py")   # only IMPORTS edges recorded
    out = capsys.readouterr().out
    assert "recorded incoming edges" in out
    assert "scanner-visible edges only" in out
    # after recording an intent edge, the caveat drops
    run(repo, "link", "src/app.py", "CALLS", "src/db.py")
    capsys.readouterr()
    run(repo, "show", "src/db.py")
    assert "scanner-visible edges only" not in capsys.readouterr().out


def test_manual_edges_survive_rescan_and_sync(repo):
    run(repo, "init")
    run(repo, "link", "src/app.py", "CALLS", "db:orders")
    # edit the file -> sync rescans it; the hand-recorded edge must survive
    with open(os.path.join(repo, "src", "app.py"), "a") as f:
        f.write("\nX = 1\n")
    run(repo, "sync", "--files", "src/app.py")
    g = Graph.load(repo)
    assert {"to": "db:orders", "type": "CALLS"} in g.nodes["src/app.py"].edges
    run(repo, "scan")  # full rescan must preserve it too
    g = Graph.load(repo)
    assert {"to": "db:orders", "type": "CALLS"} in g.nodes["src/app.py"].edges


def test_external_nodes_db_mcp(repo, capsys):
    run(repo, "init")
    run(repo, "plan", "db:orders", "--existing", "-t", "ServiceDef",
        "-s", "Order ledger; written only by app")
    run(repo, "plan", "mcp:router::search", "--existing", "-t", "ServiceDef",
        "-s", "Semantic search tool")
    g = Graph.load(repo)
    assert g.nodes["db:orders"].status == "ok"
    run(repo, "drift", expect_exit=0)          # externals are never ghosts
    run(repo, "link", "src/app.py", "CALLS", "db:orders")
    capsys.readouterr()
    run(repo, "show", "db:orders")
    assert "src/app.py" in capsys.readouterr().out
    run(repo, "mark-delete", "db:orders", expect_exit=1)   # caller recorded
    run(repo, "mark-delete", "mcp:router::search", expect_exit=0)
    g = Graph.load(repo)
    assert "mcp:router::search" not in g.nodes  # externals retire immediately
    run(repo, "drift", expect_exit=0)
    # the classification is OPEN — any invented scheme and type work
    run(repo, "plan", "erp:sap::orders", "--existing", "-t", "ErpObject",
        "-s", "SAP order master; synced nightly")
    run(repo, "link", "src/app.py", "REFERENCES", "erp:sap::orders")
    run(repo, "drift", expect_exit=0)
    g = Graph.load(repo)
    assert g.nodes["erp:sap::orders"].type == "ErpObject"


def test_graph_file_is_sorted_and_stable(repo):
    run(repo, "init")
    p = os.path.join(repo, ".graphcoding", "graph.jsonl")
    names = [json.loads(l)["name"] for l in open(p) if l.strip()]
    assert names == sorted(names)
    before = open(p).read()
    run(repo, "scan")
    assert open(p).read() == before  # idempotent rescan
