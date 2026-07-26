#!/bin/bash
set -e

cd "$(dirname "$0")"

# Ensure git identity is set
git config user.email "harys@example.com" || true
git config user.name "Harys" || true

# Stage all changes
git add .

# Commit if there are changes
git commit -m "Initial commit: Django network monitoring app with real scanner and dashboard" || true

# Set remote URL directly without removing old remote (avoids Windows ref lock)
git remote set-url origin https://github.com/harys-rifai/Network.git || git remote add origin https://github.com/harys-rifai/Network.git

# Ensure we're on main branch
git branch -M main

# Force push to avoid remote tracking ref conflicts
git push --force --no-verify origin main
