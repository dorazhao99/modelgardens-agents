import sys
from pathlib import Path
from dotenv import load_dotenv
import dspy

load_dotenv()

# Ensure project root (parent of `dev`) is on sys.path when executed directly
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dev.agents.agent import Agent, AgentResult
from dev.agents.gdrive.drive_tools import DriveTools
from dev.agents.tools.query_gum import GumTools

class GoogleDriveActions(dspy.Signature):
    """Given a task and some project context, alongside a set of Google Drive tools, take the appropriate actions to complete the task.  

You may need to search for files, read files, create documents, or edit documents.  You should use whatever tools you need to complete the task and build context as you go.

At the end, please output a summary of what you did to complete the task as well as a artifact_uri that contains a pointer to the file that was created or edited."""
    project_name: str = dspy.InputField(description="The name of the project that we are working on.")
    project_context: str = dspy.InputField(description="Some additional context about the project that we are working on.  It may contain information about the files, documents, or other resources that are relevant to the task.  This is context that you can use to help you complete the task, but it is not the primary task.")
    task_context: str = dspy.InputField(description="The primary task that we are working on.  This is the only task that you need to focus on.")
    artifact_uri: str = dspy.OutputField(description="A pointer to the file that was created or edited.")
    summary: str = dspy.OutputField(description="A summary of what you did to complete the task.")

class GoogleDriveAgent(Agent):
    def __init__(self, model: dspy.LM, name: str):
        super().__init__("GoogleDriveAgent", "A Google Drive agent that can search for/read files and create documents.  It can also edit/comment on documents.")
        self.drive_tools = DriveTools()
        self.gum_tools = GumTools(name=name, model="gpt-4.1")
        self.model = model or dspy.settings.lm
        self.google_drive_actions = dspy.ReAct(GoogleDriveActions, tools=[self.drive_tools.search_files, self.drive_tools.get_file_as_text, self.drive_tools.create_google_doc, self.drive_tools.suggest_edit, self.gum_tools.search_user_data])

    def run(self, project_name: str, project_context: str, task_context: str) -> AgentResult:
        with dspy.context(lm=self.model):
            result = self.google_drive_actions(
                project_name=project_name,
                project_context=project_context,
                task_context=task_context
            )
            return AgentResult(success=True, message=result.summary, artifact_uri=result.artifact_uri)

if __name__ == "__main__":
    model = dspy.LM('openai/gpt-5', temperature=1.0, max_tokens=16000)
    dspy.configure(lm=model)

    google_drive_agent = GoogleDriveAgent(model, name="Michael Ryan")
    result = google_drive_agent.run(project_name="AutoMetrics Release", project_context="""# AutoMetrics Release

## Ongoing Objectives
[0] Refactor code in page.tsx, focusing on enhancing presentation functionality for the upcoming Stanford AI Seminar. It is essential to ensure code clarity and final performance optimizations. (confidence: 9)
[1] Finalize integration of all software components, ensuring they work seamlessly and are optimized for the upcoming Stanford AI Seminar. Last-minute tests and adjustments may be necessary. (confidence: 9)
[2] Finalize API configurations and enhance monitoring strategies to ensure optimal performance during the demo at the Stanford AI Seminar. Prepare for any last-minute adjustments. (confidence: 9)
[3] Document current project objectives, focusing on updates relevant to the Stanford AI Seminar. (confidence: 9)
[4] Prepare and finalize presentation slides and documentation for the Stanford AI Seminar, ensuring alignment with overall project objectives and team communication strategies. (confidence: 9)
[5] Finalize Firestore Security Rules to ensure that the Firestore rules are correctly implemented for safe access and modifications based on user authentication before the Stanford AI Seminar. (confidence: 8)

## Completed Objectives
None

## Suggestions
[0] Conduct thorough testing of Firestore Security Rules to ensure safe access and modifications based on user authentication before the Stanford AI Seminar. (confidence: 8)
[1] Ensure all Firebase connectivity issues are resolved in time for the Stanford AI Seminar to guarantee smooth functionality during the demo. (confidence: 9)
[2] Implement regular check-ins to track progress on resolving Firebase connectivity issues and ensure alignment among team members as they prepare for the Stanford AI Seminar on 10/17. (confidence: 9)

## Notes
[0] Prepare project summary to present at the Stanford AI Seminar on 10/17, focusing on recent developments and objectives. (confidence: 8)
[1] Emphasize the importance of clear communication during the Stanford AI Seminar and ensure all team members are aligned on messaging. (confidence: 9)
[2] Ensure API configurations are finalized and optimized for the Stanford AI Seminar demo. (confidence: 9)
[3] Ensure team members are aware of their roles and contributions for the Stanford AI Seminar on 10/17. (confidence: 9)
[4] Emphasize testing of all integration components to identify any issues quickly before the Stanford AI Seminar. (confidence: 9)
[5] Prepare for a dry run to test the presentation flow and content delivery before the Stanford AI Seminar. (confidence: 9)
[6] Keep monitoring the completion of ongoing objectives and make any necessary adjustments before the Stanford AI Seminar. (confidence: 9)
[7] Organize a final checklist for team alignment and responsibilities before the Stanford AI Seminar on 10/17. (confidence: 8)
[8] Highlight the importance of practicing the presentation and fine-tuning final details ahead of the Stanford AI Seminar. (confidence: 9)
[9] Conduct last-minute checks on integration components and presentation materials to ensure readiness for the Stanford AI Seminar on 10/17. (confidence: 9)
[10] Consider adding a checklist to monitor completion of ongoing objectives and enhance organization for the Stanford AI Seminar. Emphasize documenting clear communication strategies among team members to ensure alignment and preparedness. (confidence: 8)
[11] Emphasize the urgency of conducting final testing on all integration components and presentation materials to ensure everything is functioning correctly ahead of the Stanford AI Seminar. (confidence: 9)
[12] Reiterate the importance of final checks and feedback collection from team members on presentation materials to ensure smooth execution at the Stanford AI Seminar. (confidence: 9)
[13] Emphasize the importance of practicing the presentation and conducting a dry run to ensure cohesion and identify last-minute adjustments before the Stanford AI Seminar. (confidence: 9)
[14] Emphasize urgency in final preparations for the Stanford AI Seminar on 10/17, suggesting a team review meeting to resolve remaining issues and ensure readiness. (confidence: 9)
[15] Verify the completion of all ongoing objectives and tasks to ensure readiness for the Stanford AI Seminar and the IRB review on 10/17. (confidence: 9)
[16] Encourage timely communication among team members regarding their roles and responsibilities to enhance overall readiness for the Stanford AI Seminar and IRB review. (confidence: 9)
[17] Establish a structured timeline for completing all ongoing objectives to enhance accountability and readiness for the Stanford AI Seminar and IRB review on 10/17. (confidence: 9)
[18] Reinforce the team's focus on specific tasks and establish deadlines for ongoing objectives to ensure timely completion ahead of the Stanford AI Seminar and IRB review. (confidence: 9)
[19] Clarify ongoing tasks and establish deadlines to ensure all preparations are aligned for the Stanford AI Seminar and IRB review on 10/17. (confidence: 9)
[20] Encourage regular check-ins among team members on their assigned tasks and deadlines in the lead-up to the Stanford AI Seminar and IRB review on 10/17. (confidence: 9)
[21] Reinforce the importance of structured communication and task ownership among team members as they prepare for the Stanford AI Seminar and IRB review on 10/17. (confidence: 9)
[22] Prioritize final checks for integration tests and address Firebase connectivity issues before the Stanford AI Seminar on 10/17. (confidence: 9)
[23] Emphasize the need to resolve any remaining Firebase connectivity issues to ensure smooth functionality before the Stanford AI Seminar on 10/17. (confidence: 9)
[24] Confirm completion of all preparation tasks and objectives to ensure full readiness for the Stanford AI Seminar on 10/17. (confidence: 9)
[25] Emphasize the importance of ongoing communication with the team regarding the resolution of Firebase connectivity issues to ensure smooth functionality before the Stanford AI Seminar on 10/17. (confidence: 9)
[26] Emphasize the importance of regular updates and clarifications among team members regarding their tasks and responsibilities as the Stanford AI Seminar approaches on 10/17. (confidence: 9)
[27] Emphasize the necessity of daily updates for effective coordination among team members as they work towards the Stanford AI Seminar on 10/17. (confidence: 9)
[28] Emphasize the necessity of maintaining clear communication channels and daily updates among team members to ensure alignment as the Stanford AI Seminar on 10/17 approaches. (confidence: 9)
[29] Emphasize the importance of resolving any Firebase connectivity issues to ensure functionality is consistent before the Stanford AI Seminar on 10/17. Ensure final testing is conducted. (confidence: 9)
[30] Emphasize regular team alignment and communication to ensure all objectives are met effectively before the Stanford AI Seminar on 10/17. (confidence: 9)

## Files, Repos, Folders, Collaborators, and Other Relevant Resources
[0] autometics-site: Main project repository for AutoMetrics development. (uri: src/app/) (confidence: 8)
[1] page.tsx: TypeScript file that may contain a React component. (uri: src/app/page.tsx) (confidence: 8)
[2] layout.tsx: Layout file for the AutoMetrics site. (uri: src/app/layout.tsx) (confidence: 8)
[3] demo.props.ts: File for demo properties used in the project. (uri: src/app/demo.props.ts) (confidence: 8)
[4] autometrics-demo: Firestore database for AutoMetrics demo. (uri: console.cloud.google.com/FireStoreDatabases/autometrics-demo) (confidence: 9)
[5] IRB Review Preparation Materials: Gather necessary documents and prepare for the upcoming IRB review meeting for project compliance. (confidence: 8)

## Next Steps
[0] Finalize project documentation and prepare an engaging presentation for the Stanford AI Seminar to ensure clear and effective communication of project objectives and developments. (confidence: 9)
[1] finalize the integration of all software components and ensure they function correctly together. (confidence: 7)
[2] Finalize monitoring of API configurations and make last-minute tweaks for optimization ahead of the seminar. (confidence: 8)
[3] Finalize and compile a detailed summary of project objectives and progress for the Stanford AI Seminar on 10/17. (confidence: 9)
[4] Finalize project documentation and prepare a presentation for the Stanford AI Seminar to effectively communicate recent developments. (confidence: 9)
[5] Reach out to team members to ensure they have the necessary information and resources for alignment with project objectives ahead of the Stanford AI Seminar. (confidence: 8)
[6] Finalize presentation materials and ensure all documentation is complete for the Stanford AI Seminar. Prepare for a dry run to test the presentation flow and content delivery. (confidence: 9)
[7] Conduct final integration tests for all software components to ensure they function correctly together ahead of the Stanford AI Seminar. (confidence: 9)
[8] Finalize API configurations and conduct monitoring checks to ensure optimal performance during the demo at the Stanford AI Seminar. (confidence: 9)
[9] Finalize presentation materials and review slides for the Stanford AI Seminar to ensure they effectively convey project objectives and developments. (confidence: 9)
[10] Finalize and enhance project documentation to ensure clarity and effectiveness for the Stanford AI Seminar. (confidence: 9)
[11] Emphasize reaching out to team members to consolidate all necessary information and ensure everyone is prepared for the Stanford AI Seminar. (confidence: 9)
[12] Conduct a final review meeting with the team to ensure alignment on all presentation components and address any remaining issues ahead of the Stanford AI Seminar. (confidence: 9)
[13] Finalize API configurations and ensure all components are tested thoroughly to guarantee optimal performance during the Stanford AI Seminar. (confidence: 9)
[14] Conduct a final review meeting with the team to address any last-minute issues and ensure alignment on all presentation components ahead of the Stanford AI Seminar. (confidence: 9)
[15] Ensure all presentation materials are finalized and conduct thorough testing on all integration components to guarantee a smooth presentation at the Stanford AI Seminar. (confidence: 9)
[16] Gather last-minute feedback on presentation materials from team members to ensure they are fully prepared for the Stanford AI Seminar. (confidence: 8)
[17] Maintain communication with team members about their roles and responsibilities while gathering last-minute feedback on presentation materials to ensure smooth execution at the Stanford AI Seminar. (confidence: 9)
[18] Finalize monitoring of API configurations and make last-minute tweaks for optimization ahead of the Stanford AI Seminar. (confidence: 9)
[19] Finalize the integration of all software components to ensure they function correctly together ahead of the Stanford AI Seminar. (confidence: 9)
[20] Finalize presentation materials and ensure all components are ready for the upcoming Stanford AI Seminar. (confidence: 9)
[21] Emphasize the urgency of final testing on all integration components and presentation materials before the Stanford AI Seminar to ensure everything functions correctly. (confidence: 9)
[22] Resolve Firebase Connectivity Issues: Address the transport errors and ensure that the application can successfully communicate with Firestore before the Stanford AI Seminar on 10/17. (confidence: 8)
[23] Conduct thorough testing of the application to identify the root cause of Firebase connectivity issues and resolve them before the Stanford AI Seminar on 10/17. (confidence: 9)
[24] Emphasize team alignment on finalizing presentation materials and practicing the presentation for the Stanford AI Seminar. Ensure that all team members are prepared and aware of their roles. (confidence: 9)
[25] Ensure that the team is aligned and prepared for final integration tests and finalize presentation materials for the Stanford AI Seminar. Highlight the necessity of clear role communication among team members. (confidence: 9)
[26] Address remaining Firebase connectivity issues to ensure functionality is consistent before the Stanford AI Seminar. (confidence: 9)
[27] Conduct a final review meeting with the team to ensure alignment on all presentation components and address any last-minute issues ahead of the Stanford AI Seminar. (confidence: 9)
[28] Resolve remaining Firebase connectivity issues to ensure functionality is consistent before the Stanford AI Seminar. (confidence: 9)
[29] Prioritize resolving Firebase connectivity issues to ensure consistent functionality before the Stanford AI Seminar on 10/17. (confidence: 9)
[30] Organize a final review meeting with the team to ensure all objectives are met effectively and reinforce the importance of ongoing communication in the lead-up to the Stanford AI Seminar on 10/17. (confidence: 9)
""", task_context="Finalize and compile a detailed summary of project objectives and progress for the Stanford AI Seminar on 10/17.")
    print(result)