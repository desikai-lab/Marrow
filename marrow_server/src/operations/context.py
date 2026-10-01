import asyncio

from tools import get_guideline_logic, get_session_context_logic


async def get_session_context(project: str, start_role: str | None = None) -> str:
    return await asyncio.to_thread(get_session_context_logic, project, start_role)


async def get_guideline(project: str, role: str) -> str:
    return await asyncio.to_thread(get_guideline_logic, project, role)
