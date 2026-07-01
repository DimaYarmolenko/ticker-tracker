#!/usr/bin/env bash
# Full deployment of ticker-tracker to the Mimir K3s cluster.
#
# Does the whole thing, in order:
#   1. build the arm64 image and import it into the node's containerd  (skip: --skip-image)
#   2. ensure the namespace exists
#   3. sync the Secret from the repo-root .env file (single source of truth, like compose)
#   4. kubectl apply -k k8s/   (postgres, app, ingress)
#   5. roll the pods so any changed .env values are picked up
#   6. wait for both rollouts to become ready
#
# Usage:
#   ./k8s/deploy.sh                 # build image + deploy
#   ./k8s/deploy.sh --skip-image    # deploy only (manifests/.env changed, image unchanged)
#   ENV_FILE=/path/to/.env ./k8s/deploy.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${HERE}/.." && pwd)"

NAMESPACE="${NAMESPACE:-ticker-tracker}"
SECRET="${SECRET:-ticker-tracker-env}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: env file not found: ${ENV_FILE}" >&2
  echo "       Set ENV_FILE=... or create ${REPO_ROOT}/.env (see .env.example)." >&2
  exit 1
fi

# 1. Image
if [[ "${1:-}" == "--skip-image" ]]; then
  echo ">> [1/6] Skipping image build/import (--skip-image)"
else
  echo ">> [1/6] Building and importing image..."
  "${HERE}/build-and-import.sh"
fi

# 2. Namespace
echo ">> [2/6] Ensuring namespace '${NAMESPACE}'..."
kubectl apply -f "${HERE}/namespace.yaml"

# 3. Secret from .env (create-or-update; apply of a dry-run render is idempotent)
echo ">> [3/6] Syncing secret '${SECRET}' from ${ENV_FILE}..."
kubectl create secret generic "${SECRET}" \
  --namespace "${NAMESPACE}" \
  --from-env-file="${ENV_FILE}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 4. Manifests
echo ">> [4/6] Applying manifests..."
kubectl apply -k "${HERE}"

# 5. Roll pods (envFrom secret changes do not restart pods on their own)
echo ">> [5/6] Restarting deployments to pick up current .env values..."
kubectl -n "${NAMESPACE}" rollout restart deploy/postgres deploy/app

# 6. Wait
echo ">> [6/6] Waiting for rollouts..."
kubectl -n "${NAMESPACE}" rollout status deploy/postgres --timeout=120s
kubectl -n "${NAMESPACE}" rollout status deploy/app --timeout=180s

echo
echo ">> Deployed. Reach the app at http://ticker.mimir.local"
echo "   (one-time: add '192.168.0.100  ticker.mimir.local' to your Mac's /etc/hosts)"
