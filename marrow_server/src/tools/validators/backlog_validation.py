

def validate_task_title_unique(new_title: str, existing_tasks: list[dict], project: str):
    """
    Validates that the task title is unique among existing tasks.
    Comparison is case-insensitive.
    """
    clean_title = new_title.strip().lower()
    for task in existing_tasks:
        if task.get("title", "").strip().lower() == clean_title:
            raise ValueError(f"A task with the title '{new_title}' already exists in project {project}. Duplicates are not allowed.")
