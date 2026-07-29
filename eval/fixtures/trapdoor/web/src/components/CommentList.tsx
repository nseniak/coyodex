// CommentList — one tiny presentational component.
//
// TRAP G1: `web/src/components/` is file-per-component. The FILE cap (10 files per component)
// fires long before the LOC cap here, so E counts 14 tiny files as unit-sized mass and lands
// far above the honest altitude. `preindex --report` says which cap bound E and prints the
// median file size — that is the signal that turns a blind disagreement into a decision.
import { h } from "../runtime";

export interface CommentListProps {
  tenant: string;
  busy?: boolean;
}

export function CommentList(props: CommentListProps) {
  if (props.busy) {
    return h("div", { class: "commentlist busy" }, "…");
  }
  return h("div", { class: "commentlist" }, props.tenant);
}

export default CommentList;
