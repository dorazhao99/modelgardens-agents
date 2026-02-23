#!/usr/bin/env bash

uv run python entry.py \
  --task '
    You are a capable agent that will help execute the following task:
    
You are a research agent that is tasked with finding all of the relevant content about a user that would be necessary to complete the following action. 

This context will be handed off to a separate agent that will use it to complete the action, so make sure to find **all** of the relevant content. It is better to have too much context than too little. Make sure to do a thorough and complete search.

You should make use of the MCP servers to find the relevant content.

Use context from the GUM MCP to interpret documents and other information that you find.

# Input
ACTION:
Weekly Schedule Review & Conflict Spotter
The agent will pull all of the user'\''s events for the upcoming week from her calendar, identify scheduling conflicts, flag events that may require preparation (e.g., lab meetings, 1:1s, fellowship events), and surface open time blocks she can use for focused work or personal tasks.

USER INPUT
{"week_start_date":"February 22, 2026","output_preference":"Document text"}

# Output
Return just the relevant context that you found and nothing else:
{{
"message": "Explain the context that you found and why it is relevant to the action",    
"context": [Detailed list of all the relevant context about the user that would be necessary to complete the action]
}}

    ' \
  --credentials /Users/dorazhao/Documents/needfinder-app/assets \
  --db_path "/Users/dorazhao/Library/Application Support/DARTBoard/app.db"
