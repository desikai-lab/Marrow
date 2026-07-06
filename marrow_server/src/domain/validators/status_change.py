from domain.validation import Validator
from utils.exceptions import ValidationError


class StatusChangeValidator(Validator):
    """Rule BS-2.5: resolution (>=5 chars) required when status changes."""

    def __init__(self, current_entry: dict, new_data: dict) -> None:
        self._current = current_entry
        self._new = new_data

    def validate(self) -> None:
        new_status = self._new.get("status")
        if not new_status:
            return
        old_status = self._current.get("status", "").lower()
        if old_status == new_status.lower():
            return
        resolution = self._new.get("resolution", "").strip()
        if not resolution or len(resolution) < 5:
            raise ValidationError(
                f"Field 'resolution' (min 5 chars) required when changing status "
                f"from '{old_status}' to '{new_status.lower()}'.",
                details={"old_status": old_status, "new_status": new_status.lower()},
            )
