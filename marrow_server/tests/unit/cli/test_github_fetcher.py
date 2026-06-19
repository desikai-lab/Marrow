import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from cli.services.github_fetcher import GitHubFetcher, GitHubFetchError, SkillNotFoundError


def test_parse_owner_repo_valid_url_returns_tuple():
    assert GitHubFetcher.parse_owner_repo("https://github.com/owner/repo") == ("owner", "repo")


def test_parse_owner_repo_trailing_slash_returns_tuple():
    assert GitHubFetcher.parse_owner_repo("https://github.com/owner/repo/") == ("owner", "repo")


def test_parse_owner_repo_invalid_url_raises_value_error():
    with pytest.raises(ValueError):
        GitHubFetcher.parse_owner_repo("https://notgithub.com/owner/repo")


@patch("urllib.request.urlopen")
def test_fetch_skill_not_found_raises_skill_not_found_error(mock_urlopen):
    err = urllib.error.HTTPError("http://api.github.com", 404, "Not Found", {}, None)
    mock_urlopen.side_effect = err

    fetcher = GitHubFetcher("https://github.com/owner/repo")
    with pytest.raises(SkillNotFoundError):
        fetcher.fetch_skill("some-skill", "some-dest")


@patch("urllib.request.urlopen")
def test_fetch_skill_api_error_raises_github_fetch_error(mock_urlopen):
    err = urllib.error.HTTPError("http://api.github.com", 500, "Internal Server Error", {}, None)
    mock_urlopen.side_effect = err

    fetcher = GitHubFetcher("https://github.com/owner/repo")
    with pytest.raises(GitHubFetchError):
        fetcher.fetch_skill("some-skill", "some-dest")


@patch("urllib.request.urlopen")
def test_fetch_skill_single_file_writes_to_dest(mock_urlopen, tmp_path):
    fetcher = GitHubFetcher("https://github.com/owner/repo")

    mock_response = MagicMock()
    mock_response.read.return_value = b'[{"type": "file", "name": "SKILL.md", "path": "skills/some-skill/SKILL.md", "download_url": "https://raw.githubusercontent.com/owner/repo/main/skills/some-skill/SKILL.md"}]'

    with patch.object(fetcher, "_download_file") as mock_download:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = fetcher.fetch_skill("some-skill", str(tmp_path))

        assert result == ["SKILL.md"]
        mock_download.assert_called_once_with(
            "https://raw.githubusercontent.com/owner/repo/main/skills/some-skill/SKILL.md",
            os.path.join(str(tmp_path), "SKILL.md"),
        )


@patch("urllib.request.urlopen")
def test_fetch_skill_recurses_into_subdirectory(mock_urlopen, tmp_path):
    fetcher = GitHubFetcher("https://github.com/owner/repo")

    mock_response_dir = MagicMock()
    mock_response_dir.read.return_value = (
        b'[{"type": "dir", "path": "skills/some-skill/subdir", "name": "subdir"}]'
    )

    mock_response_file = MagicMock()
    mock_response_file.read.return_value = b'[{"type": "file", "name": "docs.md", "path": "skills/some-skill/subdir/docs.md", "download_url": "https://raw.githubusercontent.com/owner/repo/main/skills/some-skill/subdir/docs.md"}]'

    mock_urlopen.return_value.__enter__.side_effect = [mock_response_dir, mock_response_file]

    with patch.object(fetcher, "_download_file") as mock_download:
        result = fetcher.fetch_skill("some-skill", str(tmp_path))

        assert result == ["subdir/docs.md"]
        mock_download.assert_called_once_with(
            "https://raw.githubusercontent.com/owner/repo/main/skills/some-skill/subdir/docs.md",
            os.path.join(str(tmp_path), "subdir", "docs.md"),
        )
