import argparse
import os
import sys
import modelgarden.mcp_servers.drive.server as drive
import modelgarden.mcp_servers.ical.server as ical
import modelgarden.mcp_servers.gum.server as gum
import mcp_server_fetch


def main(server_type: str, credentials_path: str | None = None, db_path: str | None = None):
    if server_type == "drive":
        if credentials_path:
            creds_path = os.path.expanduser(credentials_path)
            if os.path.isdir(creds_path):
                os.environ["GOOGLE_CREDENTIALS_JSON"] = os.path.join(creds_path, "credentials.json")
                os.environ["GOOGLE_TOKEN_PICKLE"] = os.path.join(creds_path, "token.pickle")
            else:
                os.environ["GOOGLE_CREDENTIALS_JSON"] = creds_path
        return drive.main(credentials_path=credentials_path)
    elif server_type == "ical":
        return ical.main()
    elif server_type == "gum":
        return gum.main(db_path=db_path)
    elif server_type == "fetch":
        # Set arguments for mcp_server_fetch
        original_argv = sys.argv.copy()
        sys.argv = [sys.argv[0], '--ignore-robots-txt', '--user-agent=ModelGarden/1.0']
        try:
            return mcp_server_fetch.main()
        finally:
            sys.argv = original_argv
    else:
        raise ValueError(f"Invalid server type: {server_type}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MCP Server")
    parser.add_argument("--server_type", type=str, required=True, help="Type of server to run (drive, ical, fetch)")
    parser.add_argument("--credentials_path", type=str, default=None, help="Path to credentials folder or file")
    parser.add_argument("--db_path", type=str, default=None, help="Path to SQLite3 database file")
    args = parser.parse_args()
    main(args.server_type, args.credentials_path, args.db_path)