#!/usr/bin/env bash
# GCE deployment script for instock-validator
# Usage: ./scripts/deploy-gce.sh
# Prerequisites: gcloud CLI installed and authenticated

set -euo pipefail

# ── Config — override via env vars ────────────────────────────────────────────
PROJECT_ID="${GCP_PROJECT_ID:?Set GCP_PROJECT_ID}"
INSTANCE_NAME="${GCE_INSTANCE:-instock-validator}"
ZONE="${GCE_ZONE:-europe-west1-b}"
MACHINE_TYPE="${GCE_MACHINE_TYPE:-e2-small}"   # 2GB RAM — Chromium needs headroom
DISK_SIZE="${GCE_DISK_SIZE:-20GB}"
# ──────────────────────────────────────────────────────────────────────────────

REMOTE_DIR="/opt/instock-validator"

check_gcloud() {
  if ! command -v gcloud &>/dev/null; then
    echo "ERROR: gcloud CLI not found. Install from https://cloud.google.com/sdk/docs/install"
    exit 1
  fi
  gcloud config set project "$PROJECT_ID"
}

create_vm() {
  echo "==> Creating VM: $INSTANCE_NAME ($MACHINE_TYPE) in $ZONE"

  gcloud compute instances create "$INSTANCE_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --boot-disk-size="$DISK_SIZE" \
    --boot-disk-type="pd-standard" \
    --image-family="debian-12" \
    --image-project="debian-cloud" \
    --tags="instock-validator" \
    --metadata=startup-script='#!/bin/bash
set -e
apt-get update -qq
apt-get install -y --no-install-recommends docker.io docker-compose-v2
systemctl enable --now docker
usermod -aG docker '"$(whoami)"'
' \
    --scopes="cloud-platform"

  echo "==> VM created. Waiting 30s for startup script to finish..."
  sleep 30
}

vm_exists() {
  gcloud compute instances describe "$INSTANCE_NAME" --zone="$ZONE" &>/dev/null
}

copy_project() {
  echo "==> Copying project files to VM..."

  # Create remote directory
  gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" -- \
    "sudo mkdir -p $REMOTE_DIR && sudo chown \$(whoami): $REMOTE_DIR"

  # Sync project files (exclude local artifacts)
  gcloud compute scp --recurse \
    --zone="$ZONE" \
    --exclude=".git,data,__pycache__,.env,*.pyc" \
    . \
    "$INSTANCE_NAME:$REMOTE_DIR"
}

configure_env() {
  echo "==> Configuring environment..."

  if [ ! -f .env ]; then
    echo "WARNING: .env not found locally — copying .env.example to VM as .env"
    gcloud compute scp --zone="$ZONE" .env.example "$INSTANCE_NAME:$REMOTE_DIR/.env"
  else
    gcloud compute scp --zone="$ZONE" .env "$INSTANCE_NAME:$REMOTE_DIR/.env"
  fi

  # Create data directories on VM
  gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" -- \
    "mkdir -p $REMOTE_DIR/data/reports"
}

start_service() {
  echo "==> Building and starting instock-validator..."

  gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" -- \
    "cd $REMOTE_DIR && docker compose up -d --build"

  echo "==> Service started."
  echo ""
  echo "Useful commands (run via: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE):"
  echo "  docker compose -f $REMOTE_DIR/docker-compose.yml logs -f"
  echo "  docker compose -f $REMOTE_DIR/docker-compose.yml ps"
  echo "  python $REMOTE_DIR/scripts/report.py"
}

redeploy() {
  echo "==> Redeploying (VM already exists)..."
  copy_project
  configure_env
  gcloud compute ssh "$INSTANCE_NAME" --zone="$ZONE" -- \
    "cd $REMOTE_DIR && docker compose up -d --build"
}

# ── Firewall: block inbound, allow SSH ────────────────────────────────────────
setup_firewall() {
  # Default SSH (22) is already open. Nothing else needed — service has no public port.
  echo "==> Firewall OK (SSH only, no inbound ports needed)"
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  check_gcloud

  if vm_exists; then
    echo "VM '$INSTANCE_NAME' already exists — redeploying..."
    redeploy
  else
    create_vm
    setup_firewall
    copy_project
    configure_env
    start_service
  fi

  VM_IP=$(gcloud compute instances describe "$INSTANCE_NAME" \
    --zone="$ZONE" --format="get(networkInterfaces[0].accessConfigs[0].natIP)")

  echo ""
  echo "==> Done! VM external IP: $VM_IP"
  echo "==> SSH: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
  echo "==> Logs: gcloud compute ssh $INSTANCE_NAME --zone=$ZONE -- 'docker compose -f $REMOTE_DIR/docker-compose.yml logs -f'"
}

main "$@"
