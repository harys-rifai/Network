#!/bin/bash
set -e

# Initialize git only if not already a repo
if [ ! -d .git ]; then
  git init
fi

git add .
git commit -m "Initial commit: Django network monitoring app with real scanner and dashboard" || true

# Remove any stale remote tracking refs that commonly fail on Windows
git remote remove origin || true
rm -rf .git/logs/refs/remotes/origin || true

git remote add origin https://github.com/harys-rifai/Network.git
git branch -M main

# Force push to avoid remote tracking ref issues on Windows
git push --force origin main
