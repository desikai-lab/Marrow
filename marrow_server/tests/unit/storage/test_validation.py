import pytest
from storage.validation import validate_status_change

def test_validate_status_change_same_status_does_not_raise():
    """Verifies that no error is raised if the status has not changed (case-insensitive)."""
    current = {"status": "open"}
    new = {"status": "open"}
    # Should not raise ValueError
    validate_status_change(current, new)

def test_validate_status_change_case_only_difference_does_not_raise():
    """Verifies that case-only changes are not treated as status changes."""
    current = {"status": "active"}
    new = {"status": "ACTIVE"}
    validate_status_change(current, new)

def test_validate_status_change_missing_resolution_raises_value_error():
    """Verifies that status changes require a resolution field."""
    current = {"status": "open"}
    new = {"status": "closed", "resolution": ""}
    
    with pytest.raises(ValueError, match="is required when changing status"):
        validate_status_change(current, new)

def test_validate_status_change_short_resolution_raises_value_error():
    """Verifies minimum resolution length (5 characters)."""
    current = {"status": "active"}
    new = {"status": "done", "resolution": "fix"}
    
    with pytest.raises(ValueError, match="minimum 5 characters"):
        validate_status_change(current, new)

def test_validate_status_change_valid_status_and_resolution_does_not_raise():
    """Successful validation."""
    current = {"status": "active"}
    new = {"status": "done", "resolution": "Fixed in v2.0"}
    validate_status_change(current, new)
