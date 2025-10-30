from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AgentResult:
    success: bool
    message: str
    artifact_uri: str

class Agent(ABC):

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    async def run(self, project_name: str, project_context: str, task_context: str) -> AgentResult:
        return AgentResult(success=False, message="Agent not implemented", artifact_uri="")