import sys
import os
import argparse

# Fix stdout/stderr BEFORE any imports in PyInstaller bundles
# This prevents "I/O operation on closed file" errors
# if getattr(sys, 'frozen', False):
#     # Running in PyInstaller bundle - unconditionally replace stdout/stderr
#     try:
#         sys.stdout = open(os.devnull, 'w', buffering=1)
#         sys.stderr = open(os.devnull, 'w', buffering=1)
#     except Exception:
#         # If that fails, try creating in-memory streams
#         import io
#         sys.stdout = io.StringIO()
        # sys.stderr = io.StringIO()

from modelgarden.cli.mcp_agent_cli import main

if __name__ == "__main__":
    # try:
    main()
    # except (ValueError, OSError) as e:
    #     # Handle closed file descriptor errors gracefully
    #     if "closed file" in str(e):
    #         pass  # Ignore closed file errors
    #     else:
    #         print(e)
    #         raise