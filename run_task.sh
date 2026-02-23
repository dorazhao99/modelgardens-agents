#!/usr/bin/env bash

uv run python entry.py \
  --task '
    You are a capable agent that will help execute the following task. You have already completed the first step of the task, which is to find the relevant context about the user which is provided as CONTEXT. In this step, you must use the context to complete the remaining parts of task. 
    
    Do **NOT** use the MCP servers EXCEPT to write any artifacts created. 
    
TASK:
Weekly Schedule Review & Conflict Spotter
The agent will pull all of the user'\''s events for the upcoming week from her calendar, identify scheduling conflicts, flag events that may require preparation (e.g., lab meetings, 1:1s, fellowship events), and surface open time blocks she can use for focused work or personal tasks.

USER INPUT
{"week_start_date":"February 22, 2026","output_preference":"Document text"}

CONTEXT: 

    ' \
  --credentials /Users/dorazhao/Documents/needfinder-app/assets \
  --db_path "/Users/dorazhao/Library/Application Support/DARTBoard/app.db"
