#!/usr/bin/env python3
"""
Setup script to help users configure credentials for MCP Agent.

This script checks for required credentials and provides step-by-step
instructions for obtaining them.
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple


def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def print_section(text: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'─' * 70}")
    print(f"  {text}")
    print(f"{'─' * 70}\n")


def check_status(credentials_path: str = "") -> Tuple[List[str], List[str]]:
    """Check current credential status."""
    missing = []
    found = []
    
    # Check .env file
    env_path = Path(".env")
    if not env_path.exists():
        missing.append(".env file")
    else:
        found.append(".env file")
    
    # Check OpenAI API key
    if not os.environ.get("OPENAI_API_KEY"):
        missing.append("OPENAI_API_KEY (in .env)")
    else:
        found.append("OPENAI_API_KEY")
    
    # Check Google credentials
    credentials_path = Path(credentials_path, "credentials.json"))
    if not credentials_path.exists():
        missing.append(f"Google Drive credentials ({credentials_path})")
    else:
        found.append(f"Google Drive credentials ({credentials_path})")
    
    return found, missing


def show_openai_instructions() -> None:
    """Show instructions for setting up OpenAI API key."""
    print_section("📝 Setting up OpenAI API Key")
    
    print("1. Go to: https://platform.openai.com/api-keys")
    print("2. Click 'Create new secret key'")
    print("3. Copy the key (it starts with 'sk-')")
    print("4. Create or edit the .env file in this directory:")
    print()
    print("   echo 'OPENAI_API_KEY=your-key-here' >> .env")
    print()
    print("5. Replace 'your-key-here' with your actual key")
    print()
    print("💡 Tip: Keep your .env file secure and never commit it to git!")


def show_google_drive_instructions() -> None:
    """Show instructions for setting up Google Drive credentials."""
    print_section("📝 Setting up Google Drive (Optional)")
    
    print("Google Drive integration allows the agent to:")
    print("  • Search for files and folders")
    print("  • Read Google Docs, Sheets, and Slides")
    print("  • Create and edit Google Docs")
    print()
    print("Follow these steps:")
    print()
    print("1. Go to Google Cloud Console:")
    print("   https://console.cloud.google.com/")
    print()
    print("2. Create a new project (or select existing one)")
    print()
    print("3. Enable required APIs:")
    print("   • Google Drive API:")
    print("     https://console.cloud.google.com/apis/library/drive.googleapis.com")
    print("   • Google Docs API:")
    print("     https://console.cloud.google.com/apis/library/docs.googleapis.com")
    print()
    print("4. Create OAuth 2.0 credentials:")
    print("   • Go to: https://console.cloud.google.com/apis/credentials")
    print("   • Click 'Create Credentials' → 'OAuth client ID'")
    print("   • Application type: 'Desktop app'")
    print("   • Name it something like 'MCP Agent'")
    print("   • Click 'Create'")
    print()
    print("5. Download the credentials:")
    print("   • Click the download icon (⬇) next to your new credential")
    print("   • Save it as 'credentials.json' in this directory")
    print()
    print("6. Configure OAuth consent screen (if prompted):")
    print("   • User type: External")
    print("   • Add required scopes:")
    print("     - https://www.googleapis.com/auth/drive")
    print("     - https://www.googleapis.com/auth/documents")
    print()
    print("7. On first run, the agent will open a browser to authorize access")
    print("   and save a token.pickle file for future use.")
    print()
    print("🔒 Security note: credentials.json is specific to YOUR Google Cloud")
    print("   project. Keep it secure and don't share it publicly.")


def show_optional_services() -> None:
    """Show instructions for optional services."""
    print_section("🔧 Optional Services")
    
    print("These services enhance the agent but aren't required:")
    print()
    
    print("• Brave Search (for web search):")
    print("  1. Get API key: https://api.search.brave.com/app/keys")
    print("  2. Add to .env: BRAVE_API_KEY=your-key-here")
    print()
    
    print("• GitHub (for code repository tasks):")
    print("  1. Create token: https://github.com/settings/tokens/new")
    print("  2. Required scopes: repo, pull_request, workflow")
    print("  3. Add to .env: GITHUB_TOKEN=your-token-here")
    print()
    
    print("• Calendar (iCal format):")
    print("  1. Get your calendar's ICS URL")
    print("  2. Add to .env: CALENDAR_ICS=https://your-calendar-url.ics")


def test_credentials() -> None:
    """Test if credentials are working."""
    print_section("🧪 Testing Credentials")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test OpenAI
    print("Testing OpenAI API key...")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  ❌ OPENAI_API_KEY not found")
    elif not api_key.startswith("sk-"):
        print("  ⚠️  OPENAI_API_KEY doesn't look valid (should start with 'sk-')")
    else:
        print("  ✓ OPENAI_API_KEY found and looks valid")
    
    # Test Google Drive
    print("\nChecking Google Drive credentials...")
    credentials_path = Path(os.environ.get("GOOGLE_CREDENTIALS_JSON", "credentials.json"))
    if not credentials_path.exists():
        print(f"  ○ Not found at: {credentials_path}")
        print("  → Google Drive features will be disabled")
    else:
        print(f"  ✓ Found at: {credentials_path}")
        try:
            import json
            with open(credentials_path) as f:
                creds = json.load(f)
                if "installed" in creds or "web" in creds:
                    print("  ✓ Credentials file format looks valid")
                else:
                    print("  ⚠️  Credentials file format may be incorrect")
        except Exception as e:
            print(f"  ⚠️  Error reading credentials: {e}")


def main(credentials_path: str = "") -> None:
    """Main setup workflow."""
    print_header("MCP Agent Credential Setup")
    
    print("This script will help you set up credentials for the MCP Agent.")
    
    # Check current status
    found, missing = check_status(credentials_path)
    
    if found:
        print("✓ Found:")
        for item in found:
            print(f"  • {item}")
    
    if missing:
        print("\n○ Missing:")
        for item in missing:
            print(f"  • {item}")
    
    if not missing:
        print("\n🎉 All credentials are configured!")
        test_credentials()
        print("\n✓ You're ready to use the MCP Agent!")
        print("\nRun: python -m modelgarden.cli.mcp_agent_cli")
        return
    
    
    if "Google Drive" in " ".join(missing):
        show_google_drive_instructions()
    
    show_optional_services()
    
    # Offer to test
    print_section("✅ Next Steps")
    print("1. Follow the instructions above to obtain missing credentials")
    print("2. Run this script again to verify: python setup_credentials.py")
    print("3. Once everything is set up, run: python -m modelgarden.cli.mcp_agent_cli")
    print()
    
    response = input("Would you like to test your current credentials now? [y/N]: ").strip().lower()
    if response in ['y', 'yes']:
        test_credentials()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
