#!/bin/bash
set -e

export GIT_TERMINAL_PROMPT=0

# Initialize git only if not already a repo
if [ ! -d .git ]; then
  git init
fi

git add .
git commit -m "Initial commit: Django network monitoring app with real scanner and dashboard" || true

# Clean up stale remote tracking refs that fail on Windows
git remote remove origin || true
rm -rf .git/logs/refs/remotes/origin || true

git remote add origin https://github.com/harys-rifai/Network.git
git branch -M main

# Use force push to avoid remote tracking ref issues on Windows
git push --force --no-verify origin main
