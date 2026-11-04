// Floating drawer with two buttons that even out the focused tab's panes.
// It only opens the key mods (pane-equalize-width/height), so the work lives
// in one place. Placed by a layout as a floating block with `peek`:
// each row keeps its icon on the edge side, so the peeking strip shows icons.

import { View, div, svg } from "gpui-kit";
import { h_flex, v_flex } from "gpui-base";
import { placement, run, theme } from "herdr";

const BUTTONS = [
  { axis: "width", label: "Even widths", key: "⌘⌥=" },
  { axis: "height", label: "Even heights", key: "⌘⌥⇧=" },
];

export default class PaneEqualizeBar extends View {
  button(b, mirror) {
    const t = theme();
    const icon = svg(`mods/pane-equalize-bar/${b.axis}.svg`).size(16).flex_none();
    const text = v_flex()
      .child(div().text_size(12).text_color(t.foreground).child(b.label))
      .child(div().text_size(10).text_color(t.muted).child(b.key));
    // gap is wide so the layout's peek strip (40px) shows the icon alone
    return h_flex()
      .id(`eq-${b.axis}`)
      .gap(18)
      .px(9)
      .py(6)
      .rounded(6)
      .items_center()
      .text_color(t.muted)
      .cursor_pointer()
      .hover((s) => s.bg(t.hover).text_color(t.foreground))
      .on_click(() => run("mod.open", { name: `pane-equalize-${b.axis}` }))
      .children(mirror ? [text, icon] : [icon, text]);
  }

  render() {
    const p = placement();
    const mirror = p?.edge === "right";
    const list = p && !p.vertical ? h_flex() : v_flex();
    return list.gap(2).children(BUTTONS.map((b) => this.button(b, mirror)));
  }
}
