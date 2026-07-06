import pytest
from domain.enums import TaskPriority, TaskStatus, TaskType
from models import TaskInput
from pydantic import ValidationError


def test_TaskStatus_Value_MatchesString():
    assert TaskStatus.open == "open"
    assert TaskStatus.in_progress == "in_progress"
    assert TaskStatus.paused == "paused"
    assert TaskStatus.done == "done"
    assert TaskStatus.closed == "closed"


def test_TaskPriority_Value_MatchesString():
    assert TaskPriority.critical == "critical"
    assert TaskPriority.high == "high"
    assert TaskPriority.medium == "medium"
    assert TaskPriority.low == "low"


def test_TaskType_Value_MatchesString():
    assert TaskType.feature == "F"
    assert TaskType.bug == "B"
    assert TaskType.tech_debt == "TD"


def test_TaskInput_DefaultStatus_IsOpen():
    task = TaskInput(
        type=TaskType.feature, title="Test Task", problem="Problem", solution="Solution"
    )
    assert task.status == TaskStatus.open


def test_TaskInput_InvalidType_RaisesValidationError():
    with pytest.raises(ValidationError):
        # Invalid type string
        TaskInput(type="INVALID", title="Test Task", problem="Problem", solution="Solution")


def test_TaskInput_InvalidStatus_RaisesValidationError():
    with pytest.raises(ValidationError):
        # Invalid status string
        TaskInput(
            type=TaskType.feature,
            title="Test Task",
            problem="Problem",
            solution="Solution",
            status="flying",
        )


def test_TaskInput_ModelDump_SerializesStrings():
    task = TaskInput(
        type=TaskType.feature, title="Test Task", problem="Problem", solution="Solution"
    )
    dump = task.model_dump()
    assert dump["status"] == "open"
    assert isinstance(dump["status"], str)
    assert dump["priority"] == "medium"
    assert isinstance(dump["priority"], str)
    assert dump["type"] == "F"
    assert isinstance(dump["type"], str)
