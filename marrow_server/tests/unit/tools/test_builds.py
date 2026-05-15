from tools.builds import BuildResult

def test_BuildResult_defaultConstruction_hasExpectedDefaults():
    result = BuildResult(success=True)
    assert result.output_path is None
    assert result.steps_run == 0
    assert result.warnings == []
    assert result.error is None

def test_BuildResult_modelDump_containsAllFiveKeys():
    result = BuildResult(success=True, output_path="/out/x.md", steps_run=3)
    dump = result.model_dump()
    assert set(dump.keys()) == {"success", "output_path", "steps_run", "warnings", "error"}
    assert dump["success"] is True
    assert dump["warnings"] == []
    assert dump["output_path"] == "/out/x.md"
    assert dump["steps_run"] == 3

def test_BuildResult_failurePath_hasSuccessFalseAndError():
    result = BuildResult(success=False, error="Manifest not found")
    assert result.success is False
    assert result.error == "Manifest not found"
    assert result.model_dump()["error"] == "Manifest not found"
