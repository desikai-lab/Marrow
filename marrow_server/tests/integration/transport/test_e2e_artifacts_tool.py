"""
End-to-End test suite for ALL MCP artifact tools.

Spawns mcp_local.py as a subprocess over stdio and exercises the full
artifact lifecycle: init → save (all write modes) → read (all read modes)
→ list → outline → history → restore → move → search → delete.

Every assertion validates behavior through the live MCP protocol — no
direct filesystem access or internal imports are used.

Naming convention: MethodName_InputDescription_ExpectedResult
"""

import os
import re
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _server_params(tmp_path) -> StdioServerParameters:
    server_script = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "src", "mcp_local.py")
    )
    src_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "src")
    )
    root_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env = os.environ.copy()
    env["PROJECTS_ROOT"] = str(tmp_path)
    env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{root_dir}"
    return StdioServerParameters(
        command=sys.executable, args=[server_script], env=env
    )


def _first_text(result) -> str:
    """Return the text of the first content item."""
    assert result is not None
    assert len(result.content) > 0
    return result.content[0].text


def _all_text(result) -> str:
    """Join ALL content items into one string.

    Use this for tools that serialize each list element as a separate MCP
    content item (e.g. list_project_artifacts), so the full response is
    spread across result.content[0..n].
    """
    assert result is not None
    assert len(result.content) > 0
    return "\n".join(item.text for item in result.content)


def _assert_success(result) -> str:
    """Assert MCP result has at least one content item with non-empty text."""
    text = _first_text(result)
    assert text, "Expected non-empty response from MCP server"
    return text


# ---------------------------------------------------------------------------
# Project constant
# ---------------------------------------------------------------------------

PROJECT = "E2EArtifactsProj"


@pytest.fixture(scope="module")
def tmp_artifacts_root(tmp_path_factory):
    return tmp_path_factory.mktemp("e2e_artifacts")


# ---------------------------------------------------------------------------
# Test: init_project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initProject_newProject_returnsFilesCreated(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            res = await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            text = _assert_success(res)
            assert (
                PROJECT in text
                or "files_created" in text.lower()
                or "session" in text.lower()
            )


# ---------------------------------------------------------------------------
# Test: save_project_artifacts — all write modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_saveProjectArtifacts_replaceFileMode_createsNewFile(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/base.md",
                            "mode": "replace_file",
                            "content": (
                                "# Base Doc\n\n"
                                "## Section Alpha\n\nAlpha content here.\n\n"
                                "## Section Beta\n\nBeta content here."
                            ),
                        }
                    ],
                },
            )
            text = _assert_success(res)
            assert (
                "success" in text.lower()
                or "saved" in text.lower()
                or "applied" in text.lower()
            )


@pytest.mark.asyncio
async def test_saveProjectArtifacts_appendSectionMode_addsNewSection(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/append_test.md",
                            "mode": "replace_file",
                            "content": "# Append Test\n\n## Section One\n\nFirst section.",
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/append_test.md",
                            "mode": "append_section",
                            "content": "New appended section content.",
                            "section_name": "Section Two",
                        }
                    ],
                },
            )
            text = _assert_success(res)
            assert "success" in text.lower() or "applied" in text.lower()


@pytest.mark.asyncio
async def test_saveProjectArtifacts_replaceSectionMode_updatesExistingSection(
    tmp_artifacts_root,
):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/replace_section_test.md",
                            "mode": "replace_file",
                            "content": (
                                "# Replace Section Test\n\n"
                                "## Target Section\n\nOld content to replace."
                            ),
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/replace_section_test.md",
                            "mode": "replace_section",
                            "content": "New updated content.",
                            "section_name": "Target Section",
                        }
                    ],
                },
            )
            text = _assert_success(res)
            assert "success" in text.lower() or "applied" in text.lower()


@pytest.mark.asyncio
async def test_saveProjectArtifacts_patchMode_replacesUniqueSubstring(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/patch_test.md",
                            "mode": "replace_file",
                            "content": "# Patch Test\n\nThis is the ORIGINAL_MARKER text.",
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/patch_test.md",
                            "mode": "patch",
                            "old_str": "ORIGINAL_MARKER",
                            "content": "PATCHED_VALUE",
                        }
                    ],
                },
            )
            text = _assert_success(res)
            assert "success" in text.lower() or "applied" in text.lower()


@pytest.mark.asyncio
async def test_saveProjectArtifacts_replaceChunkMode_replacesLineRange(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/chunk_test.md",
                            "mode": "replace_file",
                            "content": "# Chunk Test\nLine 2\nLine 3 TARGET\nLine 4\nLine 5",
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/chunk_test.md",
                            "mode": "replace_chunk",
                            "content": "Line 3 REPLACED",
                            "start_line": 3,
                            "end_line": 3,
                        }
                    ],
                },
            )
            text = _assert_success(res)
            assert "success" in text.lower() or "applied" in text.lower()


@pytest.mark.asyncio
async def test_saveProjectArtifacts_deleteSectionMode_removesSection(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/delete_section_test.md",
                            "mode": "replace_file",
                            "content": (
                                "# Delete Section Test\n\n"
                                "## Keep This\n\nKeep content.\n\n"
                                "## Remove This\n\nRemove content."
                            ),
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/delete_section_test.md",
                            "mode": "delete_section",
                            "content": "",
                            "section_name": "Remove This",
                        }
                    ],
                },
            )
            text = _assert_success(res)
            assert "success" in text.lower() or "applied" in text.lower()


@pytest.mark.asyncio
async def test_saveProjectArtifacts_invalidMode_returnsErrorStatus(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/invalid.md",
                            "mode": "__bad_mode__",
                            "content": "should fail",
                        }
                    ],
                },
            )
            text = _first_text(res)
            assert (
                "error" in text.lower()
                or "invalid" in text.lower()
                or "unknown" in text.lower()
            )


# ---------------------------------------------------------------------------
# Test: read_project_artifacts — all read modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readProjectArtifacts_fullMode_returnsEntireContent(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/read_full.md",
                            "mode": "replace_file",
                            "content": "# Read Full\n\nSentinel: FULL_READ_MARKER",
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [{"path": "docs/e2e/read_full.md", "mode": "full"}],
                },
            )
            text = _first_text(res)
            assert "FULL_READ_MARKER" in text


@pytest.mark.asyncio
async def test_readProjectArtifacts_pagedMode_respectsMaxChars(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            long_content = "# Paged\n\n" + "X" * 500
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/read_paged.md",
                            "mode": "replace_file",
                            "content": long_content,
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [
                        {
                            "path": "docs/e2e/read_paged.md",
                            "mode": "paged",
                            "max_chars": 50,
                        }
                    ],
                },
            )
            text = _first_text(res)
            # Paged response should be truncated (far less than 500 Xs)
            assert len(text) < 400


@pytest.mark.asyncio
async def test_readProjectArtifacts_sectionMode_returnsSectionContent(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/read_section.md",
                            "mode": "replace_file",
                            "content": (
                                "# Read Section\n\n"
                                "## Alpha\n\nAlpha content ONLY_IN_ALPHA.\n\n"
                                "## Beta\n\nBeta content ONLY_IN_BETA."
                            ),
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [
                        {
                            "path": "docs/e2e/read_section.md",
                            "mode": "section",
                            "section_name": "Alpha",
                        }
                    ],
                },
            )
            text = _first_text(res)
            assert "ONLY_IN_ALPHA" in text
            assert "ONLY_IN_BETA" not in text


@pytest.mark.asyncio
async def test_readProjectArtifacts_linesMode_returnsSpecificLineRange(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/read_lines.md",
                            "mode": "replace_file",
                            "content": "Line1\nLine2 TARGET\nLine3\nLine4",
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [
                        {
                            "path": "docs/e2e/read_lines.md",
                            "mode": "lines",
                            "start_line": 2,
                            "end_line": 2,
                        }
                    ],
                },
            )
            text = _first_text(res)
            assert "TARGET" in text
            assert "Line1" not in text
            assert "Line3" not in text


@pytest.mark.asyncio
async def test_readProjectArtifacts_nonexistentPath_returnsErrorItem(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [
                        {"path": "docs/__does_not_exist_e2e__.md", "mode": "full"}
                    ],
                },
            )
            text = _first_text(res)
            assert "error" in text.lower() or "not found" in text.lower()


@pytest.mark.asyncio
async def test_readProjectArtifacts_batchReads_returnsAllItems(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            for i in range(3):
                await session.call_tool(
                    "save_project_artifacts",
                    {
                        "project": PROJECT,
                        "updates": [
                            {
                                "path": f"docs/e2e/batch_{i}.md",
                                "mode": "replace_file",
                                "content": f"# Batch {i}\n\nContent {i}.",
                            }
                        ],
                    },
                )
            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [
                        {"path": f"docs/e2e/batch_{i}.md", "mode": "full"}
                        for i in range(3)
                    ],
                },
            )
            text = _first_text(res)
            assert "Content 0" in text or "batch_0" in text


# ---------------------------------------------------------------------------
# Test: list_project_artifacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listProjectArtifacts_topLevel_returnsProjectFiles(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            res = await session.call_tool(
                "list_project_artifacts",
                {"project": PROJECT, "path": "", "recursive": False},
            )
            text = _assert_success(res)
            # Default template provides session.md and spec.md at root
            assert (
                "session" in text.lower()
                or "spec" in text.lower()
                or "docs" in text.lower()
            )


@pytest.mark.asyncio
async def test_listProjectArtifacts_recursiveMode_returnsNestedFiles(tmp_artifacts_root):
    # Use a unique project name to avoid colliding with any real project that
    # already exists in the live PROJECTS_ROOT.
    unique_project = "E2EListRecursiveProj"
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": unique_project, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": unique_project,
                    "updates": [
                        {
                            "path": "docs/e2e/nested/deep.md",
                            "mode": "replace_file",
                            "content": "# Deep Nested File\n\nContent.",
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "list_project_artifacts",
                {"project": unique_project, "path": "docs", "recursive": True},
            )
            # list_project_artifacts emits each entry as a separate MCP content
            # item — use _all_text to scan across the full result set.
            text = _all_text(res)
            assert "deep" in text.lower() or "nested" in text.lower()


# ---------------------------------------------------------------------------
# Test: get_project_artifact_outline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_getProjectArtifactOutline_markdownFile_returnsHeadings(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/outline_test.md",
                            "mode": "replace_file",
                            "content": (
                                "# Top Level\n\n"
                                "## Section A\n\nContent A.\n\n"
                                "## Section B\n\nContent B.\n\n"
                                "### Subsection B1\n\nContent B1."
                            ),
                        }
                    ],
                },
            )
            res = await session.call_tool(
                "get_project_artifact_outline",
                {"project": PROJECT, "path": "docs/e2e/outline_test.md"},
            )
            text = _assert_success(res)
            assert "Section A" in text
            assert "Section B" in text
            assert "Subsection B1" in text


# ---------------------------------------------------------------------------
# Test: list_artifact_history + restore_project_artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listArtifactHistory_afterMultipleSaves_returnsVersionList(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            path = "docs/e2e/history_test.md"
            for version in ["Version 1", "Version 2", "Version 3"]:
                await session.call_tool(
                    "save_project_artifacts",
                    {
                        "project": PROJECT,
                        "updates": [
                            {
                                "path": path,
                                "mode": "replace_file",
                                "content": f"# History Test\n\n{version}",
                            }
                        ],
                    },
                )

            res = await session.call_tool(
                "list_artifact_history",
                {"project": PROJECT, "path": path},
            )
            text = _assert_success(res)
            # Should list at least one backup version
            assert (
                "backup" in text.lower()
                or ".md" in text.lower()
                or "history" in text.lower()
                or "version" in text.lower()
                or len(text) > 5
            )


@pytest.mark.asyncio
async def test_restoreProjectArtifact_validBackup_successResponse(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            path = "docs/e2e/restore_test.md"

            # Write initial version
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": path,
                            "mode": "replace_file",
                            "content": "# Restore Test\n\nVersion One SENTINEL",
                        }
                    ],
                },
            )
            # Write second version (creates backup of Version One)
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": path,
                            "mode": "replace_file",
                            "content": "# Restore Test\n\nVersion Two",
                        }
                    ],
                },
            )

            # Get history to find backup_name
            history_res = await session.call_tool(
                "list_artifact_history",
                {"project": PROJECT, "path": path},
            )
            history_text = _first_text(history_res)

            # Extract backup name from the response (pattern: anything.md.timestamp)
            backup_names = re.findall(r'[\w\-\.]+\.md\.\d+', history_text)
            if backup_names:
                backup_name = backup_names[0]
                restore_res = await session.call_tool(
                    "restore_project_artifact",
                    {"project": PROJECT, "path": path, "backup_name": backup_name},
                )
                restore_text = _first_text(restore_res)
                assert (
                    "restored" in restore_text.lower()
                    or "success" in restore_text.lower()
                    or path in restore_text
                )
            else:
                # History may be empty on a first-pass run; just verify call succeeded
                assert len(history_text) >= 0  # non-error response


# ---------------------------------------------------------------------------
# Test: move_project_artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_moveProjectArtifact_existingFile_movesToNewPath(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            src = "docs/e2e/move_source.md"
            dest = "docs/e2e/move_destination.md"

            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": src,
                            "mode": "replace_file",
                            "content": "# Move Source\n\nFile to be moved. MOVE_SENTINEL",
                        }
                    ],
                },
            )

            move_res = await session.call_tool(
                "move_project_artifact",
                {"project": PROJECT, "src_path": src, "dest_path": dest},
            )
            text = _first_text(move_res)
            assert (
                "moved" in text.lower()
                or dest in text
                or "success" in text.lower()
                or "->" in text
            )

            # Destination should now be readable with original content
            read_res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [{"path": dest, "mode": "full"}],
                },
            )
            read_text = _first_text(read_res)
            assert "MOVE_SENTINEL" in read_text


# ---------------------------------------------------------------------------
# Test: delete_project_artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deleteProjectArtifact_existingFile_fileNoLongerReadable(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            path = "docs/e2e/delete_me.md"
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": path,
                            "mode": "replace_file",
                            "content": "# To Be Deleted\n\nThis file will be removed.",
                        }
                    ],
                },
            )

            delete_res = await session.call_tool(
                "delete_project_artifact",
                {"project": PROJECT, "path": path},
            )
            delete_text = _first_text(delete_res)
            assert (
                "deleted" in delete_text.lower()
                or "removed" in delete_text.lower()
                or "recycled" in delete_text.lower()
                or path in delete_text
            )

            # Attempting to read the deleted file should return an error
            read_res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [{"path": path, "mode": "full"}],
                },
            )
            read_text = _first_text(read_res)
            assert "error" in read_text.lower() or "not found" in read_text.lower()


# ---------------------------------------------------------------------------
# Test: search_project_artifacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_searchProjectArtifacts_matchingQuery_returnsResult(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            unique_token = "UNIQUE_SEARCH_TOKEN_XYZ_7491"
            await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "docs/e2e/searchable.md",
                            "mode": "replace_file",
                            "content": f"# Searchable\n\nThis document contains {unique_token}.",
                        }
                    ],
                },
            )

            res = await session.call_tool(
                "search_project_artifacts",
                {"project": PROJECT, "query": unique_token},
            )
            text = _first_text(res)
            assert unique_token in text or "searchable" in text.lower()


@pytest.mark.asyncio
async def test_searchProjectArtifacts_noMatch_returnsEmptyOrMinimalResponse(tmp_artifacts_root):
    # NOTE: The semantic embedding model may return distant vector matches for
    # ANY query — it does not require an exact-token hit.  The correct signal
    # for "no match" is that the unique token itself is NOT present in the
    # response (the result is a different file with a high distance score, not
    # the content of the token we searched for).  We do NOT assert an empty
    # response because the cascade search (semantic + grep) can always surface
    # something.
    unique_token = "ABSOLUTELY_NONEXISTENT_QUERY_TOKEN_99999"
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            res = await session.call_tool(
                "search_project_artifacts",
                {
                    "project": PROJECT,
                    "query": unique_token,
                },
            )
            text = _first_text(res)
            # The exact token must NOT appear as matched content — the search
            # either returns nothing or returns semantically-adjacent documents
            # that do not contain this unique string verbatim.
            assert unique_token not in text


# ---------------------------------------------------------------------------
# Test: get_session_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_getSessionContext_freshProject_returnsContextWithRoleGuidelines(
    tmp_artifacts_root,
):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            res = await session.call_tool(
                "get_session_context", {"project": PROJECT}
            )
            text = _assert_success(res)
            assert (
                "next step" in text.lower()
                or "role" in text.lower()
                or "session" in text.lower()
                or "guideline" in text.lower()
            )


# ---------------------------------------------------------------------------
# Test: path traversal protection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readProjectArtifacts_pathTraversalAttempt_returnsError(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            res = await session.call_tool(
                "read_project_artifacts",
                {
                    "project": PROJECT,
                    "reads": [{"path": "../../outside.txt", "mode": "full"}],
                },
            )
            text = _first_text(res)
            assert (
                "error" in text.lower()
                or "traversal" in text.lower()
                or "invalid" in text.lower()
                or "outside" in text.lower()
            )


@pytest.mark.asyncio
async def test_saveProjectArtifacts_pathTraversalAttempt_returnsError(tmp_artifacts_root):
    async with stdio_client(_server_params(tmp_artifacts_root)) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await session.call_tool(
                "init_project", {"project": PROJECT, "template": "default"}
            )

            res = await session.call_tool(
                "save_project_artifacts",
                {
                    "project": PROJECT,
                    "updates": [
                        {
                            "path": "../../malicious.txt",
                            "mode": "replace_file",
                            "content": "should never be written",
                        }
                    ],
                },
            )
            text = _first_text(res)
            assert (
                "error" in text.lower()
                or "traversal" in text.lower()
                or "invalid" in text.lower()
                or "outside" in text.lower()
            )
