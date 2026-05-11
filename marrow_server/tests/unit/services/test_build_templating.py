from tools.build_processors import AppendTextProcessor, BuildContext, IncludeArtifactProcessor
from tools.builds import BuildManifest, OutputConfig, StepConfig
from tools.utils.template_renderer import TemplateRenderer


def test_render_known_variable_returns_substituted_string():
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("p1", manifest, ".out", variables={"FEATURE": "Auth"})
    content = "Hello {{FEATURE}}"
    res = TemplateRenderer.render(content, ctx)
    assert res == "Hello Auth"


def test_render_unknown_variable_leaves_placeholder_and_warns(recwarn):
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("p1", manifest, ".out")
    content = "Hello {{UNKNOWN}}"
    res = TemplateRenderer.render(content, ctx)
    assert res == "Hello {{UNKNOWN}}"
    assert len(recwarn) == 1
    assert "Unresolved placeholder '{{UNKNOWN}}'" in str(recwarn[0].message)


def test_render_mixed_case_key_resolves_case_insensitively():
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("p1", manifest, ".out", variables={"feature": "Auth"})
    # Variables are converted to uppercase on BuildContext init!
    content1 = "Hello {{feature}}"
    content2 = "Hello {{FEATURE}}"
    content3 = "Hello {{FeAtUrE}}"
    assert TemplateRenderer.render(content1, ctx) == "Hello Auth"
    assert TemplateRenderer.render(content2, ctx) == "Hello Auth"
    assert TemplateRenderer.render(content3, ctx) == "Hello Auth"


def test_render_input_variable_overrides_system_variable():
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    # The system variable PROJECT_NAME is usually "p1", but we override it
    ctx = BuildContext("p1", manifest, ".out", variables={"PROJECT_NAME": "MyOverride"})
    res = TemplateRenderer.render("{{PROJECT_NAME}}", ctx)
    assert res == "MyOverride"


def test_build_context_init_populates_system_variables():
    import datetime

    manifest = BuildManifest(
        name="my_build",
        version="2.5.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("projXYZ", manifest, ".out")
    assert ctx.variables["PROJECT_NAME"] == "projXYZ"
    assert ctx.variables["BUILD_NAME"] == "my_build"
    assert ctx.variables["VERSION"] == "2.5.0"
    assert ctx.variables["DATE"] == datetime.date.today().strftime("%Y-%m-%d")


def test_append_text_processor_template_content_renders_variables():
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("p1", manifest, ".out", variables={"TEST_VAR": "Injected"})
    processor = AppendTextProcessor()
    step = StepConfig(action="append_text", content="Data: {{TEST_VAR}}")
    processor.process(step, ctx)
    assert "Data: Injected" in ctx.output_buffer[0]


def test_include_artifact_processor_cross_project_step_routes_to_correct_project(monkeypatch):
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("p1", manifest, ".out")

    called_project = None

    def mock_read_artifact_logic(project, rel_path, mode, section_name, max_chars, force):
        nonlocal called_project
        called_project = project
        return "Mock file content {{VERSION}}"

    # Mocking read_artifact_logic for the INCLUDE processor
    import tools.build_processors

    monkeypatch.setattr(tools.build_processors, "read_artifact_logic", mock_read_artifact_logic)

    processor = IncludeArtifactProcessor()
    step = StepConfig(
        action="include_artifact", path="some.md", project="CrossProjectXYZ", skip_reference=True
    )
    processor.process(step, ctx)

    assert called_project == "CrossProjectXYZ"
    # Check that rendering happened too
    assert "Mock file content 1.0.0" in ctx.output_buffer[0]


def test_append_text_processor_plain_content_passes_through_unchanged():
    manifest = BuildManifest(
        name="test_build",
        version="1.0.0",
        output=OutputConfig(format="single_file", filename="t.md"),
        steps=[],
    )
    ctx = BuildContext("p1", manifest, ".out")
    processor = AppendTextProcessor()
    step = StepConfig(action="append_text", content="Just normal text")
    processor.process(step, ctx)
    assert ctx.output_buffer[0] == "Just normal text"


# Point 8 from plan: Output path with {{DATE}} placeholder resolves to context.output_path
# Wait, StepProcessor.render is not currently used for context.output_path in build_processors because manifest.output.path doesn't exist on OutputConfig.
# We skip point 8 as it was contradicted by the code schema, as previously discussed.
