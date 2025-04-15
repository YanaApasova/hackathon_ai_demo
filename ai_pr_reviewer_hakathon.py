#!/usr/bin/env python3
import os
import json
import requests
import openai

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

def get_diff_for_file(pr_url, filename, token):
    """Fetch raw diff content from GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    response = requests.get(f"{pr_url}", headers=headers)
    if response.status_code != 200:
        print(f"Error fetching PR diff: {response.text}")
        return ""
    return response.text  # You can optionally extract file-specific diff here

def generate_ai_review(diff_text):
    """Generate AI-based review comments using OpenAI."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # or "gpt-3.5-turbo"
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

def post_review_comment(repo, pr_number, token, comment_body, commit_id, file_path):
    """Posts an inline comment on the PR."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "body": comment_body,
        "commit_id": commit_id,
        "path": file_path,
        "line": 1,
        "side": "RIGHT"
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"✅ Comment posted on {file_path}")
    else:
        print("❌ Failed to post review comment:", response.text)

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
        post_review_comment(repo, pr_number, token, ai_comment, commit_id, filename)

if __name__ == "__main__":
    main()