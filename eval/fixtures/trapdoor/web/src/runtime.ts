// Minimal hyperscript stand-in so the components type-check as a tree.
export function h(tag: string, attrs: Record<string, unknown>, ...kids: unknown[]) {
  return { tag, attrs, kids };
}
