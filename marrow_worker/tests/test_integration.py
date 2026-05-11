"""
tests/test_integration.py — Integration tests: parse real snippets and assert AST shape.

These tests verify that the grammar bindings actually produce correct tree
structures for representative code in each supported language.
"""

from src.parser.dispatcher import get_parser_for_extension

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(ext: str, source: str):
    """Return root node of the parsed source."""
    parser = get_parser_for_extension(ext)
    tree = parser.parse(source.encode())
    return tree.root_node


def collect_types(node) -> set[str]:
    """Return the set of all node type strings in the entire tree."""
    types = {node.type}
    for child in node.children:
        types |= collect_types(child)
    return types


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------


class TestPython:
    SOURCE = (
        "class Greeter:\n    def hello(self, name: str) -> str:\n        return f'Hello, {name}'\n"
    )

    def test_root_is_module(self):
        root = parse(".py", self.SOURCE)
        assert root.type == "module"

    def test_no_errors(self):
        root = parse(".py", self.SOURCE)
        types = collect_types(root)
        assert "ERROR" not in types

    def test_contains_class_definition(self):
        root = parse(".py", self.SOURCE)
        types = collect_types(root)
        assert "class_definition" in types

    def test_contains_function_definition(self):
        root = parse(".py", self.SOURCE)
        types = collect_types(root)
        assert "function_definition" in types


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------


class TestTypeScript:
    SOURCE = "interface User { id: number; name: string; }\nconst greet = (u: User): string => `Hello, ${u.name}`;\n"

    def test_root_is_program(self):
        root = parse(".ts", self.SOURCE)
        assert root.type == "program"

    def test_no_errors(self):
        root = parse(".ts", self.SOURCE)
        types = collect_types(root)
        assert "ERROR" not in types

    def test_contains_interface(self):
        root = parse(".ts", self.SOURCE)
        types = collect_types(root)
        assert "interface_declaration" in types

    def test_contains_arrow_function(self):
        root = parse(".ts", self.SOURCE)
        types = collect_types(root)
        assert "arrow_function" in types


# ---------------------------------------------------------------------------
# TSX  (must parse JSX without ERROR nodes)
# ---------------------------------------------------------------------------


class TestTSX:
    SOURCE = 'const App = (): JSX.Element => (\n  <div className="app"><h1>Hello</h1></div>\n);\n'

    def test_root_is_program(self):
        root = parse(".tsx", self.SOURCE)
        assert root.type == "program"

    def test_no_errors(self):
        """Core requirement: JSX must parse cleanly with the TSX grammar."""
        root = parse(".tsx", self.SOURCE)
        types = collect_types(root)
        assert "ERROR" not in types

    def test_contains_jsx_element(self):
        root = parse(".tsx", self.SOURCE)
        types = collect_types(root)
        assert "jsx_element" in types


# ---------------------------------------------------------------------------
# C#
# ---------------------------------------------------------------------------


class TestCSharp:
    SOURCE = (
        "namespace Demo {\n"
        "    public class Counter {\n"
        "        private int _count = 0;\n"
        "        public void Increment() { _count++; }\n"
        "        public int Value => _count;\n"
        "    }\n"
        "}\n"
    )

    def test_root_is_compilation_unit(self):
        root = parse(".cs", self.SOURCE)
        assert root.type == "compilation_unit"

    def test_no_errors(self):
        root = parse(".cs", self.SOURCE)
        types = collect_types(root)
        assert "ERROR" not in types

    def test_contains_class_declaration(self):
        root = parse(".cs", self.SOURCE)
        types = collect_types(root)
        assert "class_declaration" in types

    def test_contains_method_declaration(self):
        root = parse(".cs", self.SOURCE)
        types = collect_types(root)
        assert "method_declaration" in types
