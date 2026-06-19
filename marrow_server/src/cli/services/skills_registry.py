import json
import os
from datetime import UTC, datetime


class SkillAlreadyRegisteredError(Exception):
    pass


class SkillNotRegisteredError(Exception):
    pass


class SkillsRegistry:
    REGISTRY_FILENAME = ".skills-registry.json"

    def __init__(self, skills_root: str) -> None:
        self.skills_root = skills_root
        self._path = os.path.join(skills_root, self.REGISTRY_FILENAME)

    def _load(self) -> dict:
        if not os.path.exists(self._path):
            return {"skills": []}
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
                if (
                    not isinstance(data, dict)
                    or "skills" not in data
                    or not isinstance(data["skills"], list)
                ):
                    return {"skills": []}
                return data
        except (json.JSONDecodeError, OSError):
            return {"skills": []}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(self, skill_name: str, source_repo: str) -> None:
        data = self._load()
        for skill in data["skills"]:
            if skill.get("name") == skill_name:
                raise SkillAlreadyRegisteredError(f"Skill '{skill_name}' is already registered.")

        data["skills"].append(
            {
                "name": skill_name,
                "source_repo": source_repo,
                "installed_at": datetime.now(UTC).isoformat(),
            }
        )
        self._save(data)

    def remove(self, skill_name: str) -> None:
        data = self._load()
        found = False
        new_skills = []
        for skill in data["skills"]:
            if skill.get("name") == skill_name:
                found = True
            else:
                new_skills.append(skill)
        if not found:
            raise SkillNotRegisteredError(f"Skill '{skill_name}' is not registered.")
        data["skills"] = new_skills
        self._save(data)

    def get(self, skill_name: str) -> dict | None:
        data = self._load()
        for skill in data["skills"]:
            if skill.get("name") == skill_name:
                return skill
        return None

    def list_all(self) -> list[dict]:
        return self._load()["skills"]

    def update_timestamp(self, skill_name: str) -> None:
        data = self._load()
        found = False
        for skill in data["skills"]:
            if skill.get("name") == skill_name:
                skill["installed_at"] = datetime.now(UTC).isoformat()
                found = True
                break
        if not found:
            raise SkillNotRegisteredError(f"Skill '{skill_name}' is not registered.")
        self._save(data)
