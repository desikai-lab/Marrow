import pytest
from domain.validators.status_change import StatusChangeValidator
from utils.exceptions import ValidationError


def test_validate_status_unchanged_passes():
    validator = StatusChangeValidator({"status": "open"}, {"status": "open"})
    validator.validate()  # Should not raise


def test_validate_status_changed_with_resolution_passes():
    validator = StatusChangeValidator(
        {"status": "open"}, {"status": "closed", "resolution": "Fixed the root cause"}
    )
    validator.validate()  # Should not raise


def test_validate_status_changed_no_resolution_raises():
    validator = StatusChangeValidator({"status": "open"}, {"status": "closed"})
    with pytest.raises(ValidationError):
        validator.validate()


def test_validate_status_changed_short_resolution_raises():
    validator = StatusChangeValidator(
        {"status": "open"}, {"status": "closed", "resolution": "nope"}
    )
    with pytest.raises(ValidationError):
        validator.validate()
