from __future__ import annotations

import logging
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)


@dataclass
class RoleProfile:
    guideline: str
    adrs: list[str]
    playbooks: list[str] = field(default_factory=list)


class RoleProfileLoader:
    """Pure, side-effect-free loader for role_profiles.yaml.
    No I/O in __init__. Fully unit-testable in isolation.
    """

    def load(self, yaml_text: str) -> dict[str, RoleProfile]:
        """Parse YAML string -> dict[role_name, RoleProfile].
        Raises ValueError on malformed YAML or missing required keys.
        """
        try:
            data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise ValueError(f"Malformed role_profiles.yaml: {exc}") from exc

        if not isinstance(data, dict) or "roles" not in data:
            raise ValueError("role_profiles.yaml must contain a top-level 'roles' key.")

        profiles: dict[str, RoleProfile] = {}
        for role_name, cfg in data["roles"].items():
            if "guideline" not in cfg:
                raise ValueError(f"Role '{role_name}' is missing required key 'guideline'.")
            profiles[role_name] = RoleProfile(
                guideline=cfg["guideline"],
                adrs=cfg.get("adrs", []),
                playbooks=cfg.get("playbooks", []),
            )
        return profiles

    def get_profile(self, yaml_text: str, role: str) -> RoleProfile | str:
        """Return RoleProfile for role, or error string if role unknown."""
        try:
            profiles = self.load(yaml_text)
        except ValueError as exc:
            return str(exc)
        if role not in profiles:
            valid = ", ".join(sorted(profiles.keys()))
            return f"Unknown role '{role}'. Valid roles: {valid}."
        return profiles[role]

    def list_roles(self, yaml_text: str) -> list[str]:
        """Return all defined role names. Used for error messages."""
        try:
            return list(self.load(yaml_text).keys())
        except ValueError:
            return []
