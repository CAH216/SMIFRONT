#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p staticfiles
mkdir -p media

# Collect static files
python manage.py collectstatic --noinput --clear

# Run migrations
python manage.py migrate

# List static files for debugging
echo "Static files collected:"
ls -la staticfiles/