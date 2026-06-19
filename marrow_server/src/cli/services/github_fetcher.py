import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse


class SkillNotFoundError(Exception):
    pass


class GitHubFetchError(Exception):
    pass


class GitHubFetcher:
    GITHUB_API_BASE = "https://api.github.com"
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

    def __init__(self, repo_url: str) -> None:
        self.repo_url = repo_url
        self.owner, self.repo = self.parse_owner_repo(repo_url)
        self.skill_name = None

    @staticmethod
    def parse_owner_repo(repo_url: str) -> tuple[str, str]:
        # Strip trailing slash
        url = repo_url.rstrip("/")
        parsed = urlparse(url)
        if parsed.netloc != "github.com":
            raise ValueError("Invalid host. Only github.com is supported.")

        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError(
                "Invalid repository URL. Must be in format https://github.com/owner/repo"
            )

        owner = parts[0]
        repo = parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]

        return owner, repo

    def fetch_skill(self, skill_name: str, dest_dir: str) -> list[str]:
        self.skill_name = skill_name
        return self._fetch_directory(f"skills/{skill_name}", dest_dir)

    def _fetch_directory(self, api_path: str, dest_dir: str) -> list[str]:
        url = f"{self.GITHUB_API_BASE}/repos/{self.owner}/{self.repo}/contents/{api_path}"

        headers = {"User-Agent": "Marrow-CLI"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise SkillNotFoundError(
                    f"Skill path '{api_path}' not found in repo {self.owner}/{self.repo}"
                ) from e
            raise GitHubFetchError(f"Failed to fetch directory {api_path}: {e.reason}") from e
        except Exception as e:
            raise GitHubFetchError(f"Failed to fetch directory {api_path}: {str(e)}") from e

        if not isinstance(data, list):
            raise SkillNotFoundError(f"Expected a directory at '{api_path}', but got a file.")

        written_paths = []
        for entry in data:
            if entry.get("type") == "file":
                download_url = entry.get("download_url")
                if not download_url:
                    continue

                prefix = f"skills/{self.skill_name}/"
                if entry["path"].startswith(prefix):
                    rel_path = entry["path"][len(prefix) :]
                else:
                    rel_path = entry["name"]

                local_path = os.path.normpath(os.path.join(dest_dir, rel_path))
                self._download_file(download_url, local_path)
                written_paths.append(rel_path.replace("\\", "/"))
            elif entry.get("type") == "dir":
                subdir_paths = self._fetch_directory(entry["path"], dest_dir)
                written_paths.extend(subdir_paths)

        return written_paths

    def _download_file(self, url: str, dest_path: str) -> None:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        headers = {"User-Agent": "Marrow-CLI"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req) as response:
                with open(dest_path, "wb") as f:
                    f.write(response.read())
        except urllib.error.HTTPError as e:
            raise GitHubFetchError(f"Failed to download file from {url}: {e.reason}") from e
        except Exception as e:
            raise GitHubFetchError(f"Failed to download file from {url}: {str(e)}") from e
