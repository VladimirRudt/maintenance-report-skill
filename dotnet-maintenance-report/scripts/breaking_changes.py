#!/usr/bin/env python3
"""Python equivalent of breaking-changes.ps1: discover breaking-changes docs on GitHub.

Usage: python breaking_changes.py [--framework]
"""
import json
import sys
import urllib.request


def fetch_tree(repo: str):
    uri = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    req = urllib.request.Request(uri, headers={
        "User-Agent": "PythonScript",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def print_entry(repo: str, path: str):
    filename = path.rsplit("/", 1)[-1]
    print(f"FileName     : {filename}")
    print(f"RepoFullPath : {path}")
    print(f"HtmlUrl      : https://github.com/{repo}/blob/main/{path}")


def main():
    framework = "--framework" in sys.argv[1:]

    if framework:
        repo = "dotnet/docs"
        response = fetch_tree(repo)
        for item in response.get("tree", []):
            if (item.get("type") == "blob"
                    and item["path"].startswith("docs/framework/migration-guide/")
                    and item["path"].endswith(".md")):
                print_entry(repo, item["path"])
        return

    for repo in ("dotnet/docs", "dotnet/EntityFramework.Docs"):
        response = fetch_tree(repo)
        for item in response.get("tree", []):
            if item.get("type") == "blob" and item["path"].rsplit("/", 1)[-1] == "breaking-changes.md":
                print_entry(repo, item["path"])


if __name__ == "__main__":
    main()
