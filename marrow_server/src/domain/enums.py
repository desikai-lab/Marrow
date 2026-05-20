from enum import StrEnum


class TaskStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    paused = "paused"
    done = "done"
    closed = "closed"


class TaskPriority(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class TaskType(StrEnum):
    feature = "F"
    bug = "B"
    tech_debt = "TD"
