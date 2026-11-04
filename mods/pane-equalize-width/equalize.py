#!/usr/bin/env python3
"""Even out pane widths or heights in one Herdr app tab.

Usage: equalize.py width|height <tab-id> [machine]

The app has no pane resize command (0.1.12), so this edits the split tree in
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


def apply(axis, tab_id, machine=None):
    on = {"on": machine} if machine else {}
    for attempt in (1, 2):
        got = rpc("doc.get", {"name": DOC, **on})
        value = got["value"]
        tab = find_tab(value, tab_id)
        if "root" not in tab:
            raise Unknown(f"tab {tab_id!r} has no root")
        new_root = equalize(tab["root"], axis)
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
    if len(argv) not in (3, 4) or argv[1] not in AXIS_NODE:
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
