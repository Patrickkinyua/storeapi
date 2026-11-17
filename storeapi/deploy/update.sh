#!/usr/bin/env bash
# Run on the VM from the project folder: ./deploy/update.sh
set -euo pipefail
cd "$(dirname "$0")/.."

git pull --ff-only
source venv/bin/activate
pip install -r requirements.txt -q
python manage.py migrate --noinput
python manage.py collectstatic --noinput -v0
sudo systemctl restart api
echo "Deployed $(git rev-parse --short HEAD)"
