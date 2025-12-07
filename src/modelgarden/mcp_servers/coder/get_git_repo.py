from git import Repo
import re

def get_repo_full_name(path: str):
    repo = Repo(path, search_parent_directories=True)
    remote_url = repo.remotes.origin.url  # e.g. git@github.com:XenonMolecule/autometrics-site.git
    match = re.search(r'[:/]([^/]+)/([^/]+?)(?:\.git)?$', remote_url)
    if match:
        owner, repo_name = match.groups()
        return f"{owner}/{repo_name}"
    else:
        raise ValueError(f"Could not parse remote URL: {remote_url}")

if __name__ == "__main__":
    print(get_repo_full_name("/Users/michaelryan/Documents/School/Stanford/Research/autometrics_release/autometrics-site/"))