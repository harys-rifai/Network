#!/bin/bash
set -e
git init
git add .
git commit -m "Initial commit: Django network monitoring app with real scanner and dashboard"
git remote add origin https://github.com/harys-rifai/Network.git
git branch -M main
git push -u origin main
