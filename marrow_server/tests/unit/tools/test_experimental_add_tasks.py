import asyncio
import os
import shutil
from unittest.mock import patch

import pytest
from config import PROJECTS_ROOT
from models import TaskInput
from services.task_command_service import add_tasks_logic
from storage.db import init_db
from storage.repositories import TaskRepository

# We'll use a unique test project name
TEST_PROJECT = "TestExpAddTasks"
TEST_PROJECT_PATH = os.path.join(PROJECTS_ROOT, TEST_PROJECT)

FAKE_VECTOR = [0.1] * 384


def setup_test_project():
    if os.path.exists(TEST_PROJECT_PATH):
        shutil.rmtree(TEST_PROJECT_PATH)
    os.makedirs(TEST_PROJECT_PATH, exist_ok=True)

    # Init LanceDB for this project (index.md is no longer needed for ID)
    init_db(TEST_PROJECT_PATH)


def teardown_test_project():
    if os.path.exists(TEST_PROJECT_PATH):
        shutil.rmtree(TEST_PROJECT_PATH)


@pytest.mark.asyncio
async def test_add_tasks_logic_valid_task_and_duplicate_title_raises_value_error():
    setup_test_project()
    try:
        with patch(
            "storage.repositories.task_repository.embeddings_manager.generate_vector",
            return_value=FAKE_VECTOR,
        ):
            # 1. Add single task

            task1 = TaskInput(
                type="F",
                title="Experimental Task 1",
                problem="Test problem 1",
                solution="Test solution 1",
                priority="high",
            )

            result1 = await add_tasks_logic([task1], TEST_PROJECT)
            print(f"Result 1: {result1}")
            assert "Successfully added 1 task(s)" in result1

            # 3. Test uniqueness (duplicate title)
            task_dup = TaskInput(
                type="F",
                title="Experimental Task 1",  # Duplicate
                problem="Dup problem",
                solution="Dup solution",
            )
            from utils.exceptions import ValidationError

            try:
                await add_tasks_logic([task_dup], TEST_PROJECT)
                assert False, "Should have raised ValidationError for duplicate title"
            except ValidationError as e:
                print(f"Caught expected error: {e}")
                assert "already exists" in str(e)

            print("Experimental add_tasks tests passed successfully!")
            tasks = [
                TaskInput(type="B", title="Experimental Bug 2", problem="p2", solution="s2"),
                TaskInput(type="TD", title="Experimental Debt 3", problem="p3", solution="s3"),
            ]

            result2 = await add_tasks_logic(tasks, TEST_PROJECT)
            print(f"Result 2: {result2}")
            assert "Successfully added 2 task(s)" in result2

            # Verify in DB
            repo = TaskRepository(TEST_PROJECT_PATH)
            t2 = await repo.get_by_key("B2")
            t3 = await repo.get_by_key("TD3")

            assert t2 is not None
            assert t2.title == "Experimental Bug 2"
            assert t3 is not None
            assert t3.key == "TD3"
            assert t3.id == 3

            print("Experimental add_tasks tests passed successfully!")

    finally:
        teardown_test_project()


if __name__ == "__main__":
    asyncio.run(test_add_tasks_logic_valid_task_and_duplicate_title_raises_value_error())
