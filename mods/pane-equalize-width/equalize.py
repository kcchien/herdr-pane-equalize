#!/usr/bin/env python3
"""Even out pane widths or heights in one Herdr app tab, or put every pane of
the tab side by side (row) or stacked (column) at equal sizes.

Usage: equalize.py width|height|row|column <tab-id> [machine]

The app has no pane resize command (0.1.13), so this edits the split tree in
herdr-core's "herdr-app" document directly. That document is undocumented:
any node shape we do not recognise aborts the write instead of guessing.
"""
import copy
import json
import os
import shutil
import subprocess
import sys

DOC = "herdr-app"
AXIS_NODE = {"width": "row", "height": "column"}
FLATTEN = ("row", "column")
MODES = (*AXIS_NODE, *FLATTEN)
KNOWN = {"row", "column", "block"}


class Unknown(Exception):
    pass


def span(node, along):
    """Leaf count of node along the axis that `along` ("row"/"column") lays out."""
    kind = node.get("type")
    if kind not in KNOWN:
        raise Unknown(f"unknown node type {kind!r}")
    if kind == "block":
        return 1
    kids = node.get("children")
    if not isinstance(kids, list) or not kids:
        raise Unknown(f"{kind} {node.get('id')!r} has no children")
    sizes = [span(k, along) for k in kids]
    return sum(sizes) if kind == along else max(sizes)


def equalize(root, axis):
    """Return a copy of root with every `axis` container weighted by leaf span."""
    along = AXIS_NODE[axis]
    tree = copy.deepcopy(root)

    def walk(node):
        if node["type"] == "block":
            return
        for k in node["children"]:
            walk(k)
        if node["type"] != along:
            return
        spans = [span(k, along) for k in node["children"]]
        total = sum(spans)
        for k, s in zip(node["children"], spans):
            # Weights are relative (flex-grow); the app writes no size for a
            # child of weight 1. Any other size kind (px) is not ours to touch.
            size = k.setdefault("size", {"weight": 1})
            if not isinstance(size, dict) or set(size) != {"weight"}:
                raise Unknown(f"child {k.get('id')!r} has size {size!r}")
            size["weight"] = s / total

    span(tree, along)  # validate the whole tree before touching anything
    walk(tree)
    return tree


def leaves(node):
    """The panes under node in tree order: inside each split, left before right
    and top before bottom. A 2x2 grid of two columns gives left column first."""
    if node["type"] == "block":
        return [node]
    return [b for k in node["children"] for b in leaves(k)]


def flatten(root, kind):
    """Return a copy of root as one `kind` container holding every pane, equal sizes.

    The root keeps its id and other keys (the app names it after the tab);
    the inner containers go away.
    """
    span(root, kind)  # validate the whole tree before touching anything
    if root["type"] == "block":
        return copy.deepcopy(root)
    tree = copy.deepcopy(root)
    panes = leaves(tree)
    for b in panes:
        b["size"] = {"weight": 1 / len(panes)}
    tree["type"] = kind
    tree["children"] = panes
    return tree


def find_tab(value, tab_id):
    for space in value.get("spaces", []):
        for tab in space.get("tabs", []):
            if tab.get("id") == tab_id:
                return tab
    raise Unknown(f"tab {tab_id!r} not found")


def hc_path():
    return shutil.which("hc") or os.path.expanduser("~/.local/bin/hc")


def rpc(method, params):
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
    out = subprocess.run([hc_path(), "connect", "--json"], input=req + "\n",
                         capture_output=True, text=True, timeout=10)
    lines = out.stdout.splitlines()
    if not lines:
        raise RuntimeError(f"hc connect gave no reply: {out.stderr.strip()}")
    reply = json.loads(lines[0])
    if "error" in reply:
        raise RuntimeError(f"{method}: {reply['error']}")
    return reply["result"]


def local_id(tab_id, machine):
    """The app shows a remote tab as "<machine>/<id>"; that machine's own
    document stores the bare id."""
    prefix = f"{machine}/" if machine else ""
    return tab_id[len(prefix):] if prefix and tab_id.startswith(prefix) else tab_id


def apply(mode, tab_id, machine=None):
    on = {"on": machine} if machine else {}
    tab_id = local_id(tab_id, machine)
    for attempt in (1, 2):
        got = rpc("doc.get", {"name": DOC, **on})
        value = got["value"]
        tab = find_tab(value, tab_id)
        if "root" not in tab:
            raise Unknown(f"tab {tab_id!r} has no root")
        new_root = flatten(tab["root"], mode) if mode in FLATTEN else equalize(tab["root"], mode)
        if new_root == tab["root"]:
            return "already even"
        print(json.dumps(tab["root"]), file=sys.stderr)  # rollback copy
        tab["root"] = new_root
        try:
            rpc("doc.set", {"name": DOC, "value": value, "version": got["version"], **on})
            return "done"
        except RuntimeError:
            if attempt == 2:
                raise
    return "unreachable"


def main(argv):
    if any(a in ('-h', '--help') for a in argv[1:]):
        print(__doc__.strip())
        return 0
    if len(argv) not in (3, 4) or argv[1] not in MODES:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        print(apply(argv[1], argv[2], argv[3] if len(argv) > 3 and argv[3] else None))
        return 0
    except (Unknown, RuntimeError, subprocess.TimeoutExpired) as e:
        print(f"equalize: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
