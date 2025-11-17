from __future__ import annotations

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class UIManager:
    """
    Simple UI-oriented manager that can be triggered by observers.
    Real UI behavior should be implemented elsewhere; this just returns structured data.
    """

    def run_for_project(
        self,
        project_name: str,
        *,
        user_profile: str = "",
        project_description: Optional[str] = None,
        user_agent_goals: Optional[str] = None,
    ) -> Dict[str, Any]:
        # For UIManager, interpret as a project-return notification by default
        logger.info("ui_manager: run_for_project (notify project return) → %s", project_name)
        return {
            "project": project_name,
            "notification": {
                "type": "project_return",
                "message": f"Welcome back to {project_name}.",
            },
        }

