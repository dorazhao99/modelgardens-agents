import sys
from pathlib import Path
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

# Ensure project root (parent of `dev`) is on sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dev.agents.agent import Agent, AgentResult
from dev.agents.tools.fast_find import find_folders
from dev.agents.tools.get_git_repo import get_repo_full_name
from dev.agents.code.openhands_tool import run_openhands_task_with_pr_async

import dspy

class IdentifyRepositoryName(dspy.Signature):
    """Identify the possible name of the repository that we are working on.  Take in the project context and return a list of possible repository names.  If the project context contains a repository name, return that first."""
    project_name: str = dspy.InputField(description="The name of the project that we are working on")
    task_context: str = dspy.InputField(description="Detailed context about the task that we are working on.")
    project_context: str = dspy.InputField(description="Detailed context about the project that we are working on.  The Files section may contain repository names.")
    potential_repository_names: list[str] = dspy.OutputField(description="A list of possible repository names.  Only return repository names that are likely to be the repository that we are working on.  If the repo name seems like a guess or has spaces you should suggest variations of the name to help identify the true repository name as a folder name (the true repo name is unlikely to have spaces).  Variations may include removing spaces, adding hyphens, adding underscores, lowercasing, etc.")

class SelectRepositoryName(dspy.Signature):
    """Select the repository name that we are working on. Given a list of actual files and folders on the local machine, select the single path that is most likely to be the repository that we are working on.  Note that if you find subfiles of the repository name, you should select the parent folder of the subfiles as the repository path."""
    project_name: str = dspy.InputField(description="The name of the project that we are working on")
    task_context: str = dspy.InputField(description="Detailed context about the task that we are working on.")
    project_context: str = dspy.InputField(description="Detailed context about the project that we are working on.  The Files section may contain repository names.")
    actual_files_and_folders: list[str] = dspy.InputField(description="A list of actual files and folders on the local machine.")
    repository_path: str = dspy.OutputField(description="The single path that is most likely to be the repository that we are working on.  Should be a global path to the repository on the local machine.  If you have low confidence in the repository path, return None.")

class FindRepository(dspy.Module):

    def __init__(self):
        self.identify_repository_name = dspy.ChainOfThought(IdentifyRepositoryName)
        self.select_repository_name = dspy.ChainOfThought(SelectRepositoryName)


    def forward(self, project_name: str, project_context: str, task_context: str) -> str:
        potential_repository_names = self.identify_repository_name(project_name=project_name, task_context=task_context, project_context=project_context).potential_repository_names

        # print(f"Potential repository names: {potential_repository_names}")

        actual_files_and_folders = []

        for potential_repository_name in potential_repository_names:
            search_results = find_folders(potential_repository_name, max_results=5, timeout=5, backend_timeout=5)
            actual_files_and_folders.extend([str(result) for result in search_results])

        # print(f"Actual files and folders: {actual_files_and_folders}")

        repository_path = self.select_repository_name(project_name=project_name, task_context=task_context, project_context=project_context, actual_files_and_folders=actual_files_and_folders).repository_path
        return repository_path

class CodeAgent(Agent):
    def __init__(self, model: dspy.LM):
        super().__init__("CodeAgent", "A coding agent that can edit code and submit a pull request to a repository.")
        self.model = model or dspy.settings.lm
        self.find_repository = FindRepository()

    async def run(self, project_name: str, project_context: str, task_context: str) -> AgentResult:

        os.environ["SANDBOX_RUNTIME_CONTAINER_IMAGE"] = "docker.all-hands.dev/all-hands-ai/runtime:0.59-nikolaik"

        with dspy.context(lm=self.model):
            repository_path = self.find_repository(
                project_name=project_name,
                project_context=project_context,
                task_context=task_context
            )

        repo_full_name = get_repo_full_name(repository_path)
        full_task = (
            f"We are working on the {repo_full_name} repository.  "
            f"The broader project is {project_name}. Some broader details about the project are shared below ===\n"
            f"{project_context}\n===\n\n"
            f"HOWEVER I want you to focus only on this specific task: ===\n"
            f"{task_context}\n===\n\n"
            f"Please follow the following steps to complete the task: ===\n"
            f"1. Make a branch in the repository called `precursor-<task> where <task> is a single word identifying the task."
            f"2. Check out the branch."
            f"3. Investigate the repository to understand the codebase and the task."
            f"4. Edit the code in the branch to complete the task."
            f"5. Commit the changes to the branch."
            f"6. Push the changes to the branch."
            f"7. Create a pull request to the repository."
            f"You may wish to add more detailed steps to the task as you need for certain more specific tasks.  Be sure to ALWAYS create a branch and a pull request for the task."
        )

        # await the async call, not wrap in asyncio.run
        result = await run_openhands_task_with_pr_async(
            project_name=project_name,
            repo=repo_full_name,
            task=full_task,
            github_token=os.getenv("GITHUB_TOKEN")
        )

        print(f"Result: {result}")

        if result.get('final_state') == 'ERROR':
            return AgentResult(success=False, message=f"Error submitting pull request to {repo_full_name}", artifact_uri="")
        elif result.get('final_state') == 'FINISHED':
            return AgentResult(success=True, message=f"Submitted pull request to {repo_full_name} ({result.get('pr_url')})", artifact_uri=result.get('pr_url'))
        else:
            return AgentResult(success=False, message=f"Unknown final state: {result.get('final_state')}", artifact_uri="")

async def main():
    model = dspy.LM('openai/gpt-4o-mini-2024-07-18')
    dspy.configure(lm=model)

    code_agent = CodeAgent(model)
    result = await code_agent.run(project_name="AutoMetrics Release", project_context="""# AutoMetrics Release

## Ongoing Objectives
[0] Refactor Code: Refactor and debug the code in the current project to enhance performance. (confidence: 7)
[1] Complete Integration: Complete integration of all software components and ensure they work seamlessly together. (confidence: 7)
[2] Optimize API Configurations: Optimize API configurations and monitor usage statistics for better performance. (confidence: 7)
[3] Document Project Objectives: Create comprehensive documentation outlining project goals, updates, and methodologies. (confidence: 7)

## Completed Objectives
None

## Suggestions
None

## Notes
[0] Prepare project summary to present at the Stanford AI Seminar on 10/17, focusing on recent developments and objectives. (confidence: 8)

## Files, Repos, Folders, Collaborators, and Other Relevant Resources
[0] autometics-site: Main project repository for AutoMetrics development. (uri: src/app/) (confidence: 8)
[1] page.tsx: TypeScript file that may contain a React component. (uri: src/app/page.tsx) (confidence: 8)
[2] layout.tsx: Layout file for the AutoMetrics site. (uri: src/app/layout.tsx) (confidence: 8)
[3] demo.props.ts: File for demo properties used in the project. (uri: src/app/demo.props.ts) (confidence: 8)

## Next Steps
[0] Refactor the code in page.tsx to improve performance, ensuring clarity in the project documentation. (confidence: 7)
[1] finalize the integration of all software components and ensure they function correctly together. (confidence: 7)
[2] Finalize monitoring of API configurations and make last-minute tweaks for optimization ahead of the seminar. (confidence: 8)
[3] Finalize and compile a detailed summary of project objectives and progress for the Stanford AI Seminar on 10/17. (confidence: 9)""", task_context="Refactor the code in page.tsx to improve performance, ensuring clarity in the project documentation.")

#     result = await code_agent.run(project_name="Background Agents", project_context="""# Background Agents

# ## Ongoing Objectives
# [0] Improve Logging Functionality: Enhance the logging capabilities in the ObjectiveInducer class to ensure accurate data processing. (confidence: 8)
# [1] Debug JSON Serialization: Test and troubleshoot the JSON serialization process to handle complex objects without errors. (confidence: 7)
# [2] Integrate Firestore Database: Finalize the integration of the Firestore database, ensuring proper configurations and security rules are in place, and conduct a thorough review of the integration to address any outstanding issues. (confidence: 9)
# [3] Finalize configurations and security rules for the Firestore database integration to ensure data protection and access control. (confidence: 8)

# ## Completed Objectives
# None

# ## Suggestions
# [0] Incorporate findings on OpenAI API hyperparameters into the presentation materials for the IRB review and AI seminar, highlighting how these parameters affect model performance. This can provide valuable insights during the discussions. (confidence: 8)
# [1] Consider additional resources or support needed to finalize presentation materials, ensuring all aspects of the logging and debugging processes are covered effectively. (confidence: 7)
# [2] Schedule regular check-ins with team members to ensure alignment and address any potential roadblocks ahead of the AI Suggestion Review and Stanford AI Seminar. (confidence: 8)

# ## Notes
# [0] Upcoming meetings include: (confidence: 8)
# [1] AI Suggestion Review on 2025-10-17 10:45-11:30 PDT (confidence: 8)
# [2] Stanford AI Seminar on 2025-10-17 12:00-13:00 PDT. These will be important for sharing progress and receiving feedback. (confidence: 8)
# [3] The user is currently working on improving logging functionality in the 'ObjectiveInducer' class and debugging JSON serialization issues to ensure handling of complex objects. This is critical for the upcoming IRB review and AI seminar. (confidence: 8)
# [4] The upcoming AI Suggestion Review and Stanford AI Seminar are crucial for sharing progress and receiving feedback. Ensure all materials and code optimizations are ready beforehand. (confidence: 9)
# [5] User is researching OpenAI API hyperparameters, specifically 'top_p,' which may enhance the understanding of tools for upcoming presentations. This research aligns with the objective of preparing for the IRB review and AI seminar. (confidence: 7)
# [6] User is currently exploring Firestore database settings for potential integration into the project, which may influence ongoing objectives related to logging and data management. This exploration reflects a shift towards database functionality in the project. (confidence: 7)
# [7] Focus on finalizing presentation materials and reviewing all outstanding items before the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [8] Final preparations for the AI seminar include a strong emphasis on the logging functionality and integration of the Firestore database. Prioritize finalizing presentation materials today. (confidence: 9)
# [9] Focus on finalizing the presentation materials that highlight improvements in logging functionality and resolved JSON serialization issues for the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [10] Ensure the integration of the Firestore database is finalized and any outstanding issues are addressed before the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [11] Conduct a final review of the logging functionality to ensure everything is functioning correctly before the upcoming AI Suggestion Review and Stanford AI Seminar. This review should address any last-minute issues and prepare for potential questions during the presentations. (confidence: 9)
# [12] Conduct a thorough review of the Firestore database integration to identify and resolve any remaining issues before the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [13] Finalize all coding tasks related to logging functionality and Firestore integration to ensure they are polished and presentable for the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [14] Prepare for final adjustments needed for logging functionality and Firestore integration before the AI Suggestion Review and Stanford AI Seminar. This includes ensuring all documentation is in order for both integrations. (confidence: 9)
# [15] Ensure the integration of the Firestore database is finalized before the upcoming AI Suggestion Review and Stanford AI Seminar, as this is crucial for addressing any issues during presentations. (confidence: 9)
# [16] Incorporate feedback from Michael Bernstein regarding alignment of Background Agents with user goals into the presentation materials to enhance clarity and effectiveness. (confidence: 8)
# [17] Focus on finalizing presentation materials and completing coding tasks related to logging functionality and Firestore integration before the upcoming AI Suggestion Review and Stanford AI Seminar on 2025-10-17. (confidence: 9)
# [18] Ensure a thorough final review of logging functionality and Firestore integration is conducted to address any outstanding issues before the upcoming AI Suggestion Review and Stanford AI Seminar on 2025-10-17. This is critical for a successful presentation. (confidence: 9)

# ## Files, Repos, Folders, Collaborators, and Other Relevant Resources
# [0] Background Agents Repository: Top-level repository for the Background Agents project. (uri: dev/survey) (confidence: 9)
# [1] context_log.csv: CSV file for logging context updates. (uri: dev/survey/context_log.csv) (confidence: 9)
# [2] logger.py: Python script for logging activities. (uri: dev/survey/logger.py) (confidence: 9)
# [3] objective_inducer.py: Main script for inducing objectives. (uri: dev/survey/objective_inducer.py) (confidence: 9)
# [4] survey_responses.csv: CSV file storing survey responses. (uri: dev/survey/survey_responses.csv) (confidence: 9)
# [5] README.md: Markdown file providing project overview and documentation. (uri: dev/README.md) (confidence: 9)
# [6] requirements.txt: Text file listing project dependencies. (uri: dev/requirements.txt) (confidence: 9)

# ## Next Steps
# [0] Finalize presentation materials and ensure all code optimizations are complete before the upcoming meetings. (confidence: 9)
# [1] Review all aspects of the project and finalize any open items, ensuring everything is in order before the upcoming IRB review and AI seminar. (confidence: 8)
# [2] List specific tasks to finalize presentation materials, including key points to highlight related to logging and JSON issues. (confidence: 8)
# [3] Create an outline of the key points to cover in the presentation materials, focusing on logging and JSON serialization issues. (confidence: 8)
# [4] Detail specific tasks such as resolving logging and JSON issues, and finalizing presentation materials based on the outlined key points. (confidence: 8)
# [5] Create a detailed list of tasks for finalizing presentation materials, focusing on logging and JSON serialization issues, to ensure all points are clearly covered. (confidence: 9)
# [6] Create an outline of key points for the presentation, ensuring coverage of logging functionality and JSON serialization issues. (confidence: 9)
# [7] List specific tasks for resolving logging and JSON serialization issues, ensuring they are thoroughly addressed in the presentation materials. (confidence: 9)
# [8] Finalize the presentation materials highlighting the improved logging functionality and resolved JSON serialization issues, ensuring all points are clear and covered. (confidence: 9)
# [9] Finalize the integration of the Firestore database, ensuring all configurations and security rules are ready for demonstration at upcoming meetings. (confidence: 9)
# [10] Conduct a final review of the Firestore integration, preparing for any potential questions during the upcoming meetings, especially concerning security rules and configurations. (confidence: 9)
# [11] Finalize coding tasks related to logging functionality and Firestore integration to ensure they are polished and presentable for the upcoming meetings. (confidence: 9)
# [12] Conduct a final review of the integration of the Firestore database to address any outstanding issues before the upcoming meetings, particularly focusing on security rules and configurations. Ensure all required documentation is prepared. (confidence: 9)
# [13] List any unresolved issues with logging functionality and Firestore integration that need to be addressed in preparation for the upcoming AI Suggestion Review and Stanford AI Seminar, and create a timeline for resolving them. (confidence: 9)
# [14] Create a detailed list of tasks for finalizing presentation materials, focusing on logging and JSON serialization issues to ensure all points are clearly covered. (confidence: 9)
# [15] Detail specific tasks for resolving logging and JSON serialization issues, ensuring they are thoroughly addressed in the presentation materials. (confidence: 9)
# [16] Finalize presentation materials and ensure all code optimizations are complete before the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [17] Finalize the integration of the Firestore database and ensure all configurations and security rules are ready for demonstration at upcoming meetings. (confidence: 9)
# [18] Emphasize finalizing the presentation materials that outline improvements in logging functionality and resolved JSON serialization issues for the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [19] Conduct a final review of the logging functionality to ensure optimal performance before the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [20] Review outstanding items related to the JSON serialization process to ensure readiness for the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [21] Incorporate Michael Bernstein's feedback on aligning Background Agents with user goals into the presentation materials and refine based on this insight to improve user engagement. (confidence: 8)
# [22] Review all aspects of the logging functionality and JSON serialization issues to ensure they are effectively addressed before the upcoming AI Suggestion Review and Stanford AI Seminar. (confidence: 9)
# [23] Emphasize the completion of all coding tasks related to logging functionality and Firestore integration to ensure they are polished and ready for the upcoming AI Suggestion Review and Stanford AI Seminar on 2025-10-17. (confidence: 9)
# [24] Create a timeline for addressing any remaining issues with logging functionality and Firestore integration in preparation for the upcoming AI Suggestion Review and Stanford AI Seminar on 2025-10-17. (confidence: 8)
# """, task_context="Review all aspects of the logging functionality and JSON serialization issues to ensure they are effectively addressed before the upcoming AI Suggestion Review and Stanford AI Seminar.")

    print(result)

if __name__ == "__main__":
    asyncio.run(main())