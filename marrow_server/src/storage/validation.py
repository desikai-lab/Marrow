from typing import Any


def validate_status_change(current_entry: dict[str, Any], new_data: dict[str, Any]) -> None:
    """
    Validates that the 'resolution' field is present when changing status.
    Enforces rule BS-2.5: status changes require a justification (minimum 5 characters).
    """
    new_status = new_data.get("status")
    if not new_status:
        return
        
    old_status = current_entry.get("status", "").lower()
    if old_status == new_status.lower():
        return
        
    # Status changed — validate resolution
    resolution = new_data.get("resolution", "").strip()
    if not resolution or len(resolution) < 5:
        raise ValueError(
            f"Field 'resolution' (minimum 5 characters) is required when changing status from '{old_status}' to '{new_status.lower()}'."
        )
