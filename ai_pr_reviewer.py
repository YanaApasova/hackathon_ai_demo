#!/usr/bin/env python3
import os
import json
import requests
import openai
import re

openai.api_key = os.environ.get("OPENAI_API_KEY")

def get_changed_files(pr_url, token):
    """Fetch list of changed files from GitHub API."""
    files_url = f"{pr_url}/files"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = requests.get(files_url, headers=headers)
    if response.status_code != 200:
        print("Error fetching changed files:", response.text)
        return []
    return response.json()

def generate_ai_review(diff_text):
    """Generate AI-based review comments using OpenAI."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior software engineer reviewing a pull request. "
                        "Give detailed, constructive feedback focusing on code quality, readability, bugs, and best practices."
                    )
                },
                {
                    "role": "user",
                    "content": f"Please review the following code diff:\n\n{diff_text}"
                }
            ],
            max_tokens=500,
            temperature=0.3
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print("⚠️ OpenAI API error:", e)
        return "Unable to generate review comment."

def find_first_changed_line(patch):
    """Parse the patch to find the first line number in the new code ('+')."""
    hunk_pattern = re.compile(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@')
    line_num = None

    for line in patch.splitlines():
        match = hunk_pattern.match(line)
        if match:
            line_num = int(match.group(1))
            continue
        if line_num is not None:
            if line.startswith('+') and not line.startswith('+++'):
                return line_num
            elif not line.startswith('-'):
                line_num += 1
    return None

def post_review_comment(repo, pr_number, token, comment_body, commit_id, file_path, patch):
    """Posts an inline comment to the PR on the actual changed line."""
    line_number = find_first_changed_line(patch)
    if not line_number:
        print(f"⚠️ Could not determine changed line for {file_path}.")
        return

    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "body": comment_body,
        "commit_id": commit_id,
        "path": file_path,
        "line": line_number,
        "side": "RIGHT"
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"✅ Inline comment posted on {file_path} at line {line_number}")
    else:
        print("❌ Failed to post inline comment:", response.text)

def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("❌ GITHUB_EVENT_PATH is not set.")
        return

    with open(event_path, "r") as f:
        event_data = json.load(f)

    pr = event_data.get("pull_request")
    if not pr:
        print("❌ No pull_request data found.")
        return

    pr_number = pr.get("number")
    pr_url = pr.get("url")
    commit_id = pr.get("head", {}).get("sha")
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")

    if not all([pr_number, pr_url, commit_id, repo, token]):
        print("❌ Missing required environment variables.")
        return

    files = get_changed_files(pr_url, token)
    if not files:
        print("No changed files detected.")
        return

    for file in files:
        filename = file["filename"]
        patch = file.get("patch")
        if not patch:
            print(f"⚠️ Skipping {filename} (no patch)")
            continue

        print(f"🔍 Reviewing {filename}...")
        ai_comment = generate_ai_review(patch)
        post_review_comment(repo, pr_number, token, ai_comment, commit_id, filename, patch)

if __name__ == "__main__":
    main()
