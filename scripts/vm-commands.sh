#!/usr/bin/env bash
# Quick reference — run these manually on the GCE VM after SSH'ing in
# gcloud compute ssh instock-validator --zone=europe-west1-b

# ── Initial VM setup (one-time) ───────────────────────────────────────────────
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker   # or log out and back in

# ── Deploy / update ───────────────────────────────────────────────────────────
cd /opt/instock-validator
docker compose up -d --build      # first deploy or after code change

# ── Day-to-day ops ────────────────────────────────────────────────────────────
docker compose logs -f                         # tail live logs
docker compose ps                              # check container status
docker compose restart instock-validator       # restart without rebuild

python scripts/report.py                       # print current summary report

# ── Smoke test (before first full run) ───────────────────────────────────────
docker compose run --rm instock-validator python scripts/smoke_test.py

# ── Update code ───────────────────────────────────────────────────────────────
# From local machine:
# gcloud compute scp --recurse --exclude=".git,data,__pycache__,.env,*.pyc" \
#   . instock-validator:/opt/instock-validator --zone=europe-west1-b
# Then on VM:
docker compose up -d --build
