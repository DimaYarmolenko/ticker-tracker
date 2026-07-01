# Deploying ticker-tracker to the Mimir K3s cluster

Kubernetes manifests (Kustomize) for running the app on the single-node K3s cluster
`mimir` (Raspberry Pi 5, arm64, `192.168.0.100` / `mimir.local`).

## What gets deployed

Namespace `ticker-tracker` containing:

| Resource | Purpose |
|----------|---------|
| `ticker-tracker-env` (Secret) | **All** env, generated from the repo-root `.env` — same source as `docker compose`. Created by `deploy.sh`, not committed. |
| `postgres.yaml` | `postgres:17-alpine` Deployment + PVC (`local-path`) + Service **named `db`** |
| `app.yaml` | FastAPI Deployment (1 replica) + Service; init-container waits for the DB |
| `ingress.yaml` | Traefik ingress at `http://ticker.mimir.local` |

Config comes entirely from the repo-root **`.env`** (see `.env.example` for the keys).
`deploy.sh` loads it into the `ticker-tracker-env` Secret and both Deployments read it
via `envFrom`. The Postgres Service is named `db` so `.env`'s `POSTGRES_HOST=db` resolves
unchanged (same name as the compose service).

The app runs `alembic upgrade head` on startup (baked into the image `CMD`) and stays at
**1 replica** on purpose — it runs an in-process scheduler; more replicas would double
every news/price poll.

## Prerequisites

- A populated `.env` at the repo root (copy from `.env.example`).
- Docker Desktop with `buildx` on the Mac (`docker buildx version`).
- `kubectl` pointed at the cluster (`kubectl get nodes` shows `mimir` Ready).
- SSH to the node: `ssh -i ~/.ssh/mimir_pi yarddim@mimir.local`.

## Deploy (one command)

```bash
./k8s/deploy.sh
```

That runs the whole flow: build the arm64 image → import it into the node's containerd →
sync the Secret from `.env` → `kubectl apply -k k8s/` → restart pods → wait for readiness.

Then, one time, add a hostname entry on the Mac so the browser resolves the ingress:

```bash
echo '192.168.0.100  ticker.mimir.local' | sudo tee -a /etc/hosts
```

Open <http://ticker.mimir.local>.

## Common operations

```bash
# Config/manifest change only (edited .env or a *.yaml), image unchanged:
./k8s/deploy.sh --skip-image

# New app code -> new image tag, then full deploy:
#   1. bump TAG in build-and-import.sh (or pass it) and the image tag in app.yaml
./k8s/build-and-import.sh 0.1.1
sed -i '' 's/ticker-tracker:0.1.0/ticker-tracker:0.1.1/' k8s/app.yaml
./k8s/deploy.sh --skip-image
```

`build-and-import.sh` only handles the **image** (build → tarball → `k3s ctr images
import`); `deploy.sh` is the full deployment and calls it as its first step. Always use a
fresh tag (not `latest`) so `imagePullPolicy: IfNotPresent` picks up the new image.

## Troubleshooting

- **`app` pod `CrashLoopBackOff`** — `kubectl -n ticker-tracker logs deploy/app`.
  Usually the DB isn't reachable or `POSTGRES_PASSWORD` in `.env` differs from what
  Postgres initialized the volume with. If you changed the password after the PVC was
  created, the old one persists in the volume — reset with
  `kubectl -n ticker-tracker delete pvc postgres-data` (destroys data) and redeploy.
- **`ErrImageNeverPull` / `ImagePullBackOff`** — the tag in `app.yaml` doesn't match an
  image imported into containerd. Check:
  `ssh -i ~/.ssh/mimir_pi yarddim@mimir.local 'sudo k3s ctr images ls | grep ticker-tracker'`.
- **404 from Traefik** — ingress host/path mismatch, or no `/etc/hosts` entry (curl with
  `-H 'Host: ticker.mimir.local'` to bypass DNS).
- **Connection refused on port 80** — confirm Traefik has the node IP:
  `kubectl -n kube-system get svc traefik` (EXTERNAL-IP should be `192.168.0.100`).
