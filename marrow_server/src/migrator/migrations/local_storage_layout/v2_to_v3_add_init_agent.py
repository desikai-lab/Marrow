import os

from common import path_resolver
from migrator.base import Migration, MigrationStepReport
from migrator.migrations.local_storage_layout.role_record import (
    INIT_PROFILE,
    INIT_ROLE,
    append_init_role,
)
from tools.utils.filesystem_utils import create_artifact_backup


class V2ToV3AddInitAgent(Migration):
    subsystem = "local_storage_layout"
    from_version = 2
    to_version = 3

    def apply(self, project_root: str, dry_run: bool = False) -> MigrationStepReport:
        report = MigrationStepReport(
            subsystem=self.subsystem, from_version=self.from_version, to_version=self.to_version
        )
        project_name = os.path.basename(os.path.abspath(project_root))

        # Read template guideline first; missing template must raise (no bump)
        import tools.projects as projects_module

        template_guideline = os.path.join(
            projects_module.TEMPLATE_DIR, "artifacts", "docs", "manuals", "guidelines", "init.md"
        )
        if not os.path.isfile(template_guideline):
            raise FileNotFoundError(template_guideline)
        guideline_bytes = open(template_guideline, "rb").read()

        # Add guideline file
        guideline_path = path_resolver.get_path(project_name, "docs/manuals/guidelines/init.md")
        if guideline_path.exists():
            report.skipped += 1
        elif dry_run:
            report.moved += 1
        else:
            try:
                abs_path = guideline_path.as_accessor_source()
                os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                with open(abs_path, "wb") as f:
                    f.write(guideline_bytes)
                report.moved += 1
            except Exception as exc:
                report.errors.append({"file": str(guideline_path.relative_path), "error": str(exc)})

        # Add role record
        rp_path = path_resolver.get_path(project_name, "docs/manuals/role_profiles.yaml")
        if not rp_path.exists():
            report.skipped += 1
            return report
        try:
            rp_text = (
                rp_path.read_text(encoding="utf-8-sig")
                if hasattr(rp_path, "read_text")
                else rp_path.read()
            )
        except Exception as exc:
            report.errors.append({"file": str(rp_path.relative_path), "error": str(exc)})
            return report

        # If already has init role
        try:
            import yaml

            parsed = yaml.safe_load(rp_text)
            roles = parsed.get("roles") if isinstance(parsed, dict) else None
            if isinstance(roles, dict) and INIT_ROLE in roles:
                existing = roles[INIT_ROLE]
                if existing == INIT_PROFILE:
                    report.skipped += 1
                else:
                    report.collisions += 1
                return report
        except Exception:
            pass

        new_text = append_init_role(rp_text)
        if new_text is None:
            report.errors.append(
                {"file": "role_profiles.yaml", "error": "manual step: add the init role"}
            )
            return report

        # Validate again
        import yaml

        old_parsed = yaml.safe_load(rp_text)
        new_parsed = yaml.safe_load(new_text)
        old_roles = old_parsed.get("roles", {}) if isinstance(old_parsed, dict) else {}
        new_roles = new_parsed.get("roles", {}) if isinstance(new_parsed, dict) else {}
        if new_roles.get(INIT_ROLE) != INIT_PROFILE:
            report.errors.append(
                {"file": "role_profiles.yaml", "error": "manual step: add the init role"}
            )
            return report
        # ensure no other roles changed
        for key in old_roles:
            if old_roles[key] != new_roles[key]:
                report.errors.append(
                    {"file": "role_profiles.yaml", "error": "manual step: add the init role"}
                )
                return report

        if dry_run:
            report.moved += 1
            return report

        try:
            create_artifact_backup(project_name, rp_path)
        except Exception as exc:
            report.errors.append(
                {"file": str(rp_path.relative_path), "error": f"backup failed: {exc}"}
            )
            return report
        try:
            rp_path.write(new_text)
        except Exception as exc:
            report.errors.append({"file": str(rp_path.relative_path), "error": str(exc)})
            return report
        report.moved += 1
        return report
