from typing import List

# -----------------------------------------------------------------------------
# simple user profile composition (shared)
# -----------------------------------------------------------------------------

def compose_user_profile(
    user_name: str | None,
    user_description: str | None,
    user_agent_goals: str | None = None,
) -> str:
    """
    Minimal, readable single-line user profile string composed from available parts.
    """
    parts: List[str] = []
    if user_name and user_name.strip():
        parts.append("Name: " + user_name.strip())
    if user_description and user_description.strip():
        parts.append("Description: " + user_description.strip())
    if user_agent_goals and user_agent_goals.strip():
        parts.append("Agent Goals (Things this user wants the agent to focus on; not exhaustive): " + user_agent_goals.strip())
    if not parts:
        return "User"
    return "\n".join(parts)