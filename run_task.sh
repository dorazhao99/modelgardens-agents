#!/usr/bin/env bash

uv run python entry.py \
  --task '
    You are a capable agent that will help execute the following task. You have already completed the first step of the task, which is to find the relevant context about the user which is provided as CONTEXT. In this step, you must use the context to complete the remaining parts of task. 
    
    Do **NOT** use the MCP servers EXCEPT to write any artifacts created. 
    
    Use the following depending on the output format:
    - Text document: For text documents, use the drive MCP to write a document. If more complicated formatting is needed, use the filesystem MCP to create a Markdown file.
    - Markdown file: Use the filesystem MCP to create a Markdown file
    - Calendar event: Create an ics file
    - Slides: Use the slides MCP to create a slides deck
    
TASK:
Weekly Schedule Review & Conflict Spotter
The agent will pull all of the user'\''s events for the upcoming week from her calendar, identify scheduling conflicts, flag events that may require preparation (e.g., lab meetings, 1:1s, fellowship events), and surface open time blocks she can use for focused work or personal tasks.

USER INPUT
{"week_start_date":"February 22, 2026","output_preference":"Document text"}

CONTEXT: 
The research agent returned the following message and context:
I retrieved Dora Zhao\s calendar for the week of February 22, 2026, and cross-referenced it with research documents and lab schedules from Google Drive. I identified several key meetings (SALT Lab, Situated Systems, Advising, LinkedIn project) and a direct conflict on March 1. I specifically found that she needs to prepare for a Deep Dive presentation for the SALT Lab on March 4, 2026, and identified the Situated Systems essay as her primary research focus. I also captured context regarding her fellowship commitments and typical preparation requirements for advisor meetings.

Dora Zhao has a SALT Lab Meeting recurring on Wednesdays; for the week of Feb 22, the calendar marks it as Canceled, but the SALT Lab Meeting Winter 2026 spreadsheet (ID: 1UYMdqkKvGNNvlJVN3KT8wI7I7M7MvE6-Cm_FRInigvM) lists Feb 25 as a One-pager day., Dora and Grace are scheduled to present a Deep Dive at the SALT Lab on March 4, 2026, which requires preparation (15-25 min presentation) during the week of Feb 22., Dora has a Situated Systems meeting on Thursday, Feb 26, involving collaborators from Stanford, MIT, and Harvard. The core document The Computer for the 2030s: Situated Systems (ID: 1GTnkNb4dCUtU-ZaBm1MWOieDjdJKwTkCajVBzSBjQoA) outlines five principles: Loyalty, Copresence, Memory, Interpretation, and Tact., Dora has a weekly advising session with Michael Bernstein and Diyi Yang on Friday, Feb 27. A relevant recent document is Advisor Communication Strategies For Research Mistakes (ID: 1BX-yMaInlThFk15IMCplb4Xgnn7J-rWx)., There is a scheduling conflict on Sunday, March 1, 2026, between Deal with Finances and Google Charges, both at 17:00., Dora is involved in a LinkedIn Workforce Skills Analysis project with Microsoft/Insight Global (weekly Fridays)., Dora has a 24-week fellowship commitment in the fall that has created conflicts with recruitment (e.g., Google roles), and she has previously applied for/held Hertz and Ford fellowships., Focused work priorities for this week include: Preparing Deep Dive slides for SALT Lab and writing/revising the Situated Systems essay.
    ' \
  --credentials /Users/dorazhao/Documents/needfinder-app/assets
