import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.build_processors import BuildContext


class TemplateRenderer:
    @staticmethod
    def render(content: str, context: "BuildContext") -> str:
        """
        Resolve {{KEY}} placeholders from context.variables.
        Keys are case-insensitive. Missing keys are left unchanged; a warning is logged.
        """

        def _replace(match: re.Match) -> str:
            key = match.group(1).upper()
            if key in context.variables:
                return context.variables[key]
            import warnings

            warnings.warn(
                f"[BUILD TEMPLATE] Unresolved placeholder '{{{{{match.group(1)}}}}}' — "
                "no variable found in context. Placeholder left as-is.",
                stacklevel=2,
            )
            return match.group(0)  # leave unchanged

        return re.sub(r"\{\{([^}]+)\}\}", _replace, content)
