// Key: mod.open:pane-equalize-row. The overlay closes itself at once and runs
// equalize.py (in mods/pane-equalize-width/) on the focused tab. The app has no pane
// resize command, so the script edits herdr-core's layout doc. Mods cannot
// import across folders, so the four pane-equalize-width/height/row/column
// mods differ only in AXIS.

import { View, div } from "gpui-kit";
import { appHome, closeOverlay, exec, focused, notify, props, spaces, window as appWindow } from "herdr";

const AXIS = "row";

export default class extends View {
  init() {
    // Close only after exec settles: closing the overlay ends this copy and
    // cancels its unfinished work (seen live: the edit was sometimes lost).
    const done = () => { const o = props()?.overlay; if (o != null) closeOverlay(o); };
    const f = focused();
    if (!f?.tab) return done();
    const machine = spaces().find((s) => s.id === f.space)?.machine ?? "";
    const fail = (body) => notify({ title: "Equalize panes failed", body, level: "error" });
    // On Windows `python3` is usually the Microsoft Store alias, not a real Python.
    const python = appWindow().platform === "windows" ? "python" : "python3";
    exec(python, [`${appHome()}/mods/pane-equalize-width/equalize.py`, AXIS, f.tab, machine])
      .then((r) => { if (r.code !== 0) fail(r.stderr.trim().split("\n").pop()); })
      .catch((e) => fail(String(e)))
      .finally(done);
  }

  render() {
    return div();
  }
}
