from __future__ import annotations

from typing import Protocol, Dict, Any, Optional


class Manager(Protocol):
    """
    Minimal protocol for observer-triggerable managers.
    Concrete managers (e.g., AgentManager, UIManager) implement a single entrypoint.
    """

    def run_for_project(
        self,
        project_name: str,
        *,
        user_profile: str = "",
        project_description: Optional[str] = None,
        user_agent_goals: Optional[str] = None,
    ) -> Dict[str, Any]:
        ...

