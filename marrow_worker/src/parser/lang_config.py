from dataclasses import dataclass


@dataclass
class LangSyntaxConfig:
    container_nodes: set[str]
    method_nodes: set[str]
    body_nodes: set[str]
    stub_text: bytes
    import_nodes: set[str]
    property_nodes: set[str]


csharp_config = LangSyntaxConfig(
    container_nodes={"namespace_declaration", "class_declaration", "interface_declaration"},
    method_nodes={"method_declaration", "constructor_declaration"},
    body_nodes={"block"},
    stub_text=b"{ /* ... implementation */ }",
    import_nodes={"using_directive"},
    property_nodes={"property_declaration", "field_declaration"},
)

ts_config = LangSyntaxConfig(
    container_nodes={"class_declaration", "interface_declaration", "namespace_declaration"},
    method_nodes={"method_definition", "function_declaration"},
    body_nodes={"statement_block"},
    stub_text=b"{ /* ... implementation */ }",
    import_nodes={"import_statement", "lexical_declaration"},
    property_nodes={"property_signature", "public_field_definition"},
)

python_config = LangSyntaxConfig(
    container_nodes={"class_definition"},
    method_nodes={"function_definition"},
    body_nodes={"block"},
    stub_text=b" pass",
    import_nodes={"import_statement", "import_from_statement"},
    property_nodes={"expression_statement"},
)

CONFIG_BY_EXT = {
    ".cs": csharp_config,
    ".js": ts_config,
    ".ts": ts_config,
    ".tsx": ts_config,
    ".jsx": ts_config,
    ".py": python_config,
}
