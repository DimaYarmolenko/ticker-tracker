#!/usr/bin/env bash
# Build the app image for arm64 on this (x86) Mac, ship it to the K3s node, and
# import it into containerd. No registry involved.
#
# Usage:  ./k8s/build-and-import.sh [TAG]
set -euo pipefail

IMAGE="${IMAGE:-ticker-tracker}"
TAG="${1:-${TAG:-0.1.0}}"
PI="${PI:-yarddim@mimir.local}"
KEY="${KEY:-$HOME/.ssh/mimir_pi}"

TAR="${IMAGE}-${TAG}-arm64.tar"
BUILDER="${BUILDER:-ticker-tracker-builder}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Cross-arch tarball export needs the docker-container driver (the default "docker"
# driver can't export images for a foreign platform). Create the builder once.
if ! docker buildx inspect "${BUILDER}" >/dev/null 2>&1; then
  echo ">> Creating buildx builder '${BUILDER}' (docker-container driver)..."
  docker buildx create --name "${BUILDER}" --driver docker-container --bootstrap
fi

echo ">> Building ${IMAGE}:${TAG} for linux/arm64..."
docker buildx build \
  --builder "${BUILDER}" \
  --platform linux/arm64 \
  --target app \
  -t "${IMAGE}:${TAG}" \
  -o "type=docker,dest=${REPO_ROOT}/${TAR}" \
  "${REPO_ROOT}"

echo ">> Copying ${TAR} to ${PI}:/tmp/ ..."
scp -i "${KEY}" "${REPO_ROOT}/${TAR}" "${PI}:/tmp/${TAR}"

echo ">> Importing into k3s containerd on the node..."
ssh -i "${KEY}" "${PI}" "sudo k3s ctr images import /tmp/${TAR} && rm -f /tmp/${TAR}"

echo ">> Done. Imported ${IMAGE}:${TAG}."
echo "   Verify: ssh -i ${KEY} ${PI} 'sudo k3s ctr images ls | grep ${IMAGE}'"
echo "   Local tarball left at ${REPO_ROOT}/${TAR} (git-ignored; safe to delete)."
