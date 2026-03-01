#!/usr/bin/env bash

set -euo pipefail

WORKFLOW_FILE=".github/workflows/pr-checks.yml"
TARGET_BRANCH="${1:-$(git branch --show-current)}"

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: GitHub CLI (gh) is not installed."
  echo "Install: https://cli.github.com/"
  exit 2
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Error: gh is not authenticated."
  echo "Run: gh auth login"
  exit 2
fi

if ! git_root="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  echo "Error: not inside a git repository."
  exit 2
fi

remote_url="$(git -C "$git_root" config --get remote.origin.url || true)"
if [[ -z "$remote_url" ]]; then
  echo "Error: remote.origin.url is not configured."
  exit 2
fi

repo="$(echo "$remote_url" | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"

run_args=(
  --repo "$repo"
  --workflow "$WORKFLOW_FILE"
  --branch "$TARGET_BRANCH"
  --limit 1
)

run_id="$(gh run list "${run_args[@]}" --json databaseId --jq '.[0].databaseId // empty')"
status="$(gh run list "${run_args[@]}" --json status --jq '.[0].status // empty')"
conclusion="$(gh run list "${run_args[@]}" --json conclusion --jq '.[0].conclusion // empty')"
url="$(gh run list "${run_args[@]}" --json url --jq '.[0].url // empty')"
title="$(gh run list "${run_args[@]}" --json displayTitle --jq '.[0].displayTitle // empty')"

if [[ -z "$run_id" ]]; then
  echo "No pipeline run found for branch '$TARGET_BRANCH' in workflow '$WORKFLOW_FILE'."
  exit 3
fi

echo "Pipeline status for '$TARGET_BRANCH':"
echo "- Workflow: PullRequest_Pipeline"
echo "- Run ID: $run_id"
echo "- Title: $title"
echo "- Status: $status"
echo "- Conclusion: ${conclusion:-n/a}"
echo "- URL: $url"

if [[ "$status" != "completed" ]]; then
  echo "Pipeline is still running."
  exit 4
fi

if [[ "$conclusion" != "success" ]]; then
  echo "Pipeline tests did not pass."
  exit 1
fi

echo "Pipeline tests passed."
