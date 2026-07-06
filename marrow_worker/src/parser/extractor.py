from dataclasses import dataclass

from tree_sitter import Node

from src.parser.dispatcher import get_parser_for_extension
from src.parser.lang_config import CONFIG_BY_EXT, LangSyntaxConfig


@dataclass
class ReplacementRange:
    start_byte: int
    end_byte: int
    stub_text: bytes


def find_replacements(node: Node, config: LangSyntaxConfig) -> list[ReplacementRange]:
    replacements = []

    def visit(n: Node):
        if n.type in config.method_nodes:
            # Found a method or constructor; find its implementation block
            for child in n.children:
                if child.type in config.body_nodes:
                    replacements.append(
                        ReplacementRange(
                            start_byte=child.start_byte,
                            end_byte=child.end_byte,
                            stub_text=config.stub_text,
                        )
                    )
                    # Do not visit children of the block; we are discarding it
                    return

        # Continue searching recursively
        for child in n.children:
            visit(child)

    visit(node)
    return replacements


def extract_skeleton(source_bytes: bytes, ext: str) -> str:
    """
    Parses the source code using Tree-sitter and returns the semantic skeleton
    by stubs out method and property implementations.
    """
    ext_lower = ext.lower()
    if ext_lower not in CONFIG_BY_EXT:
        return source_bytes.decode("utf-8", errors="replace")

    config = CONFIG_BY_EXT[ext_lower]
    parser = get_parser_for_extension(ext_lower)
    tree = parser.parse(source_bytes)

    replacements = find_replacements(tree.root_node, config)

    # Sort in descending order to prevent byte shifts during sequential replacement
    replacements.sort(key=lambda r: r.start_byte, reverse=True)

    result_bytes = source_bytes
    for r in replacements:
        result_bytes = result_bytes[: r.start_byte] + r.stub_text + result_bytes[r.end_byte :]

    return result_bytes.decode("utf-8", errors="replace")


def get_node_name(node: Node) -> str:
    """Finds the first identifier-like child of a node to act as its name."""

    for child in node.children:
        if child.type in ("identifier", "name", "type_identifier", "property_identifier"):
            return child.text.decode("utf-8", errors="ignore")
    return "unknown"


def extract_chunks(source_bytes: bytes, ext: str) -> list[dict]:
    """
    Returns a list of code units (file, class, method, property, imports) with localized skeleton strings.
    """
    ext_lower = ext.lower()
    if ext_lower not in CONFIG_BY_EXT:
        return []

    config = CONFIG_BY_EXT[ext_lower]
    parser = get_parser_for_extension(ext_lower)
    tree = parser.parse(source_bytes)

    chunks = []
    class_count = 0
    method_count = 0
    imports_text = []

    def visit(n: Node):
        nonlocal class_count, method_count
        name = None

        # 1. Capture Imports
        if n.type in config.import_nodes:
            imports_text.append(n.text.decode("utf-8", errors="ignore"))
            return

        # 2. Identify Chunk Type
        chunk_type = None
        if n.type in config.container_nodes:
            chunk_type = "class" if "class" in n.type else "namespace"
            if chunk_type == "class":
                class_count += 1
        elif n.type in config.method_nodes:
            chunk_type = "method"
            method_count += 1
        elif n.type in config.property_nodes:
            chunk_type = "property"

            # POLISH: If a property/statement is multi-line, it's likely a complex block, not a field.
            # Skipping these maintains skeleton brevity (ADR-24 Review).
            if n.end_point.row - n.start_point.row > 0:
                return

            # Simple heuristic for assignment names (extract 'x' from 'x = 1')
            text = n.text.decode("utf-8", errors="replace")
            if "=" in text:
                name = text.split("=")[0].strip().split()[-1]
            else:
                name = get_node_name(n)

        # 3. Craft Chunk if matched
        if chunk_type:
            if not name:
                name = get_node_name(n)
            # Find the body to stop grabbing text
            body_start = n.end_byte
            has_body = False
            for child in n.children:
                if child.type in config.body_nodes:
                    body_start = child.start_byte
                    has_body = True
                    break

            # The skeleton text is the signature + stub
            sig_bytes = source_bytes[n.start_byte : body_start].strip()
            if has_body:
                skel_bytes = sig_bytes + b" " + config.stub_text
            else:
                skel_bytes = sig_bytes

            chunks.append(
                {
                    "type": chunk_type,
                    "name": name,
                    "skeleton_text": skel_bytes.decode("utf-8", errors="replace"),
                    "line_start": n.start_point.row + 1,
                    "line_end": n.end_point.row + 1,
                }
            )

        for child in n.children:
            visit(child)

    visit(tree.root_node)

    # 4. File Chunk Summary improvement (ADR-24 Review)
    symbols = []
    if class_count > 0:
        class_names = [c["name"] for c in chunks if c["type"] == "class"]
        symbols.append(
            f"Classes: {', '.join(class_names[:10])}{'...' if len(class_names) > 10 else ''}"
        )
    if method_count > 0:
        method_names = [c["name"] for c in chunks if c["type"] == "method"]
        symbols.append(
            f"Methods: {', '.join(method_names[:10])}{'...' if len(method_names) > 10 else ''}"
        )

    summary_text = " | ".join(symbols) if symbols else "No structural units found."

    line_count = max(len(source_bytes.split(b"\n")), 1)
    file_chunk = {
        "type": "file",
        "name": "file",
        "skeleton_text": f"File Structure: {summary_text}",
        "line_start": 1,
        "line_end": line_count,
    }

    final_chunks = [file_chunk] + chunks

    # 5. Emitting the Imports Chunk
    if imports_text:
        final_chunks.append(
            {
                "type": "imports",
                "name": "imports",
                "skeleton_text": "\n".join(imports_text),
                "line_start": 1,
                "line_end": line_count,
            }
        )

    return final_chunks
