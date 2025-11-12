
from typing import List, Dict, Optional

import dspy

from precursor.components.task_proposer.goal_inducer import FutureGoalInducer
from precursor.components.task_proposer.milestone_inducer import MilestoneInducer
from precursor.components.task_proposer.task_scorer import BatchedTaskScorer, TaskAssessment
from precursor.components.task_proposer.agent_task_proposer import BackgroundAgentTaskProposer


def _render_goal_milestones_checklist(goal_to_milestones: Dict[str, List[str]]) -> str:
    """
    Render a mapping of {high_level_goal: [milestones...]} into a simple checklist string
    that can be fed as `important_todo_list` to the BackgroundAgentTaskProposer.
    """
    if not goal_to_milestones:
        return ""
    lines: List[str] = []
    for goal, milestones in goal_to_milestones.items():
        clean = [m.strip() for m in (milestones or []) if m]
        if not clean:
            continue
        lines.append(f"## {goal}")
        for m in clean:
            lines.append(f"- [ ] {m}")
        lines.append("")
    return "\n".join(lines).strip()


class TaskProposerPipeline(dspy.Module):
    """
    End-to-end DSPy module that chains the Task Proposer components:
      1) FutureGoalInder (ChainOfThought) -> future_goals (3-7 strategic goals)
      2) MilestoneInder (batched) per goal -> goal_to_milestones map
      3) BackgroundAgentTaskProposer -> 10 background tasks from aggregated milestones
      4) BatchedScorer -> per-task (relative) value/safety/feasibility/alignment scores

    Inputs:
      - user_profile: description of the user and their long-term goals and context
      - project_name: name of the current project
      - project_scratchpad: rendered project scratchpad text
      - project_description: optional description of the project from the user
      - user_agent_goals: optional existing agent-recorded goals or focus areas

    Returns a dict with:
      - future_goals: List[str]
      - goal_to_milestones: Dict[str, List[str]]
      - agent_tasks: List[str]
      - task_assessments: List[TaskAssessment]
    """

    def __init__(self) -> None:
        super().__init__()
        self.future_goal = dspy.ChainOfThought(FutureGoalInducer)
        self.milestone = dspy.ChainOfThought(MilestoneInducer)
        self.task_proposer = dspy.ChainOfThought(BackgroundAgentTaskProposer)
        self.task_scorer = dspy.ChainOfThought(BatchedTaskScorer)

    def forward(
        self,
        *,
        user_profile: str,
        project_name: str,
        project_scratchpad: str,
        project_description: Optional[str] = None,
        user_agent_goals: Optional[str] = None,
    ) -> dict:
        # 1) Infer future goals
        goals_pred = self.future_goal(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
        )
        future_goals: List[str] = [
            g.strip() for g in (getattr(goals_pred, "future_goals", []) or []) if g
        ]

        # 2) Induce milestones per goal (batched)
        goal_to_milestones: Dict[str, List[str]] = {}
        if future_goals:
            batch_inputs: List[dspy.Example] = []
            goals_order: List[str] = []
            for g in future_goals:
                batch_inputs.append(
                    dspy.Example(
                        user_profile=user_profile,
                        project_name=project_name,
                        project_scratchpad=project_scratchpad,
                        project_description=project_description,
                        high_level_goal=g,
                    ).with_inputs("user_profile", "project_name", "project_scratchpad", "project_description", "high_level_goal")
                )
                goals_order.append(g)
            ms_out = self.milestone.batch(batch_inputs, disable_progress_bar=True)
            for g, out in zip(goals_order, ms_out):
                ms_list = [m.strip() for m in (getattr(out, "milestones", []) or []) if m]
                goal_to_milestones[g] = ms_list

        # 3) Build checklist text from milestones
        important_todo_list = _render_goal_milestones_checklist(goal_to_milestones)

        # 4) Propose background-agent tasks
        tasks_out = self.task_proposer(
            user_profile=user_profile,
            project_name=project_name,
            project_scratchpad=project_scratchpad,
            project_description=project_description,
            important_todo_list=important_todo_list,
        )
        agent_tasks: List[str] = [
            t.strip() for t in (getattr(tasks_out, "tasks", []) or []) if t
        ]

        # 5) Score proposed tasks (batched, relative)
        assessments: List[TaskAssessment] = []
        if agent_tasks:
            score_out = self.task_scorer(
                user_profile=user_profile,
                project_name=project_name,
                project_scratchpad=project_scratchpad,
                project_description=project_description,
                high_level_goals=future_goals,
                task_descriptions=agent_tasks,
            )
            assessments = list(getattr(score_out, "assessments", []) or [])

        return {
            "future_goals": future_goals,
            "goal_to_milestones": goal_to_milestones,
            "agent_tasks": agent_tasks,
            "task_assessments": assessments,
        }

