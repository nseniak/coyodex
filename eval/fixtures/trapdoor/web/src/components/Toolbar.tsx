// Toolbar — one tiny presentational component.
//
// TRAP G1: `web/src/components/` is file-per-component. The FILE cap (10 files per component)
// fires long before the LOC cap here, so E counts 14 tiny files as unit-sized mass and lands
// far above the honest altitude. `preindex --report` says which cap bound E and prints the
// median file size — that is the signal that turns a blind disagreement into a decision.
import { h } from "../runtime";

export interface ToolbarProps {
  tenant: string;
  busy?: boolean;
}

export function Toolbar(props: ToolbarProps) {
  if (props.busy) {
    return h("div", { class: "toolbar busy" }, "…");
  }
  return h("div", { class: "toolbar" }, props.tenant);
}

export default Toolbar;
