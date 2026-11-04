"""Pure tree tests for the pane-equalize mod; no live Herdr document is touched."""
import importlib.util
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parents[1] / "mods" / "pane-equalize-width" / "equalize.py"
spec = importlib.util.spec_from_file_location("equalize", SRC)
eq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eq)


def block(i, w):
    return {"type": "block", "id": i, "content": {"terminal": i}, "size": {"weight": w}}


def node(kind, i, children, w=None):
    n = {"type": kind, "id": i, "children": children}
    if w is not None:
        n["size"] = {"weight": w}
    return n


def weights(n):
    return [round(k["size"]["weight"], 4) for k in n["children"]]


class Equalize(unittest.TestCase):
    def test_nested_rows_get_equal_widths(self):
        # cmd-d three times: 1/2, 1/4, 1/8, 1/8
        inner2 = node("row", "r2", [block("c", 0.5), block("d", 0.5)], 0.5)
        inner1 = node("row", "r1", [block("b", 0.5), inner2], 0.5)
        root = node("row", "r0", [block("a", 0.5), inner1])
        got = eq.equalize(root, "width")
        self.assertEqual(weights(got), [0.25, 0.75])
        self.assertEqual(weights(got["children"][1]), [round(1 / 3, 4), round(2 / 3, 4)])
        self.assertEqual(weights(got["children"][1]["children"][1]), [0.5, 0.5])
        self.assertEqual(root["children"][0]["size"]["weight"], 0.5, "input must not change")

    def test_column_inside_row_counts_as_one_column(self):
        col = node("column", "c0", [block("b", 0.8), block("c", 0.2)], 0.3)
        root = node("row", "r0", [block("a", 0.7), col])
        got = eq.equalize(root, "width")
        self.assertEqual(weights(got), [0.5, 0.5])
        self.assertEqual(weights(got["children"][1]), [0.8, 0.2], "width leaves heights alone")
        got = eq.equalize(root, "height")
        self.assertEqual(weights(got), [0.7, 0.3], "height leaves widths alone")
        self.assertEqual(weights(got["children"][1]), [0.5, 0.5])

    def test_wide_column_child_weighs_by_its_columns(self):
        two = node("row", "r1", [block("b", 0.5), block("c", 0.5)], 0.5)
        col = node("column", "c0", [two, block("d", 0.5)], 0.5)
        root = node("row", "r0", [block("a", 0.5), col])
        self.assertEqual(weights(eq.equalize(root, "width")), [round(1 / 3, 4), round(2 / 3, 4)])

    def test_single_pane_is_untouched(self):
        root = block("a", 1)
        self.assertEqual(eq.equalize(root, "width"), root)

    def test_unknown_type_refuses(self):
        root = node("row", "r0", [block("a", 0.5), {"type": "stack", "id": "s", "size": {"weight": 0.5}}])
        with self.assertRaises(eq.Unknown):
            eq.equalize(root, "width")

    def test_missing_size_means_weight_one(self):
        # seen live: a column split down twice is [no size, 0.5, 0.5], drawn 2:1:1
        col = node("column", "c0", [{"type": "block", "id": "a"}, block("b", 0.5), block("c", 0.5)])
        got = eq.equalize(col, "height")
        self.assertEqual(weights(got), [round(1 / 3, 4)] * 3)

    def test_px_size_refuses(self):
        root = node("row", "r0", [block("a", 0.5), {"type": "block", "id": "b", "size": {"px": 200}}])
        with self.assertRaises(eq.Unknown):
            eq.equalize(root, "width")

    def test_find_tab(self):
        value = {"spaces": [{"tabs": [{"id": "t1", "root": block("a", 1)}]}]}
        self.assertEqual(eq.find_tab(value, "t1")["id"], "t1")
        with self.assertRaises(eq.Unknown):
            eq.find_tab(value, "nope")


if __name__ == "__main__":
    unittest.main()
