"""
test_sanity.py -- Smoke-test for the SKEL-1 Foundation layer.

Run from the marrow_worker root:
    python test_sanity.py
Expected output: All 4 parse tests PASS, printing node count and a
pretty-printed AST tree for each source snippet.
"""

import sys
import io

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Holds everything collected from a single parse run."""
    node_count: int
    root_type: str
    tree_lines: list[str] = field(default_factory=list)


def _build_tree_lines(node, prefix: str = "", is_last: bool = True) -> list[str]:
    """Recursively build pretty-print lines for *node* and its children."""
    connector = "+-- " if is_last else "+-- "
    # Show node type; for named leaf nodes also show the text
    label = node.type
    if not node.children and node.is_named:
        label += f' "{node.text.decode()}"'
    lines = [prefix + connector + label]
    child_prefix = prefix + ("    " if is_last else "|   ")
    children = node.children
    for i, child in enumerate(children):
        lines += _build_tree_lines(child, child_prefix, i == len(children) - 1)
    return lines


def _parse(ext: str, source: str) -> ParseResult:
    """Parse *source* as *ext* and return a rich ParseResult."""
    from src.parser.dispatcher import get_parser_for_extension

    parser = get_parser_for_extension(ext)
    tree = parser.parse(source.encode())
    root = tree.root_node

    # Count all nodes via cursor walk
    count = 0
    cursor = tree.walk()
    reached_root = False
    while not reached_root:
        count += 1
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue
        while True:
            if not cursor.goto_parent():
                reached_root = True
                break
            if cursor.goto_next_sibling():
                break

    tree_lines = _build_tree_lines(root)
    return ParseResult(node_count=count, root_type=root.type, tree_lines=tree_lines)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

def run_tests() -> None:
    cases = [
        (".py",  "class Hello:\n    def greet(self): pass\n"),
        (".ts",  "class Hello { greet(): void {} }"),
        (".tsx", "const App = () => <div>Hello</div>;"),
        (".cs",  "class Hello { void Greet() {int i = 0; i++;} }"),
    ]

    passed = 0
    failed = 0

    for ext, source in cases:
        print(f"\n[{ext}]  source: {source.strip()!r}")
        try:
            result = _parse(ext, source)
            assert result.node_count > 1, f"Trivial parse ({result.node_count} nodes)"

            print(f"  PASS  -> {result.node_count} nodes, root={result.root_type!r}")
            print("  AST:")
            for line in result.tree_lines:
                print("    " + line)
            passed += 1
        except Exception as exc:
            print(f"  FAIL  -> {exc}", file=sys.stderr)
            failed += 1

    print("\n" + "-" * 50)
    print(f"Results: {passed} passed, {failed} failed")    

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    print("SKEL-1 Sanity Tests")
    print("=" * 50)
    run_tests()
