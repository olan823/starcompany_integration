# Versioned Image Deployment Runbook

## Purpose

Deploy `starcompany_integration` as an application baked into the ERPNext v16 image. This procedure changes only the `erpnext-prod` Compose project. It does not modify, stop, recreate, or attach networks to other Docker projects.

## Preconditions

- The app source has been pushed to a private Git repository reachable by the build host.
- The ERPNext deployment directory, Compose project name, and target site have been confirmed on the server.
- A working backup exists for the ERPNext database and `sites` volume.
- The existing ERPNext image tag and Compose configuration have been recorded for rollback.
- Starcompany has published a dedicated, authenticated read-only health endpoint below `/api/erpnext/`.
- The reverse proxy allows the ERPNext backend container to reach the Starcompany API address.

## Freeze the App Source

The image build reads the app from Git. Files copied into a running container and uncommitted local changes are not part of an image.

Use this same release path for every later Starcompany feature migration. Do not copy feature files into production containers as the normal deployment method:

1. Implement and validate the feature in `starcompany_integration`.
2. Commit and push the exact source state.
3. Create a new immutable app tag and record its full commit SHA.
4. Build only the Starcompany incremental image from the fixed ERPNext base image.
5. Update the production environment file to the new image tag.
6. Validate the resolved Compose images before deployment.
7. Recreate only the ERPNext application services with the deployment script.
8. Complete both server-side health checks and the Desk business verification.

Keep internal identifiers stable unless a migration explicitly requires changing them. For example, the Workspace and module remain `Starcompany`, the route remains `/app/starcompany-console`, and display labels such as the `授权池` shortcut may change independently.

Choose one new app version for each release and use it consistently in the Git tag and image tag. For example:

```bash
APP_VERSION=0.1.8
APP_REF="v${APP_VERSION}"
IMAGE_TAG="16.32.0-starcompany-${APP_VERSION}"
```

Never reuse or move an existing Git tag or image tag. The fixed ERPNext base image is rebuilt only when the pinned Frappe or ERPNext version changes.

Commit and push the exact app state to deploy, create an immutable release tag, then record its full commit SHA:

```bash
cd /path/to/starcompany_integration
python -m compileall starcompany_integration
git status --short
git rev-parse HEAD
git push origin HEAD
git tag -a v0.1.1 -m "starcompany_integration v0.1.1"
git push origin v0.1.1
```

The release commit must contain the P3 proxy and Desk changes. The build script verifies that the threshold update method exists in the resulting image.

## Build the Versioned Image

Run the build from the `frappe_docker` checkout with both the release tag and its full commit SHA. Bench clones the tag, and the Containerfile verifies its commit before removing Git metadata. Do not build from `main` or use `latest`:

```bash
chmod +x scripts/build-starcompany-image.sh

APP_REF=v0.1.1 \
APP_COMMIT=<full-40-character-commit-sha> \
IMAGE_TAG=16.32.0-starcompany-0.1.1 \
./scripts/build-starcompany-image.sh
```

The script confirms that the remote tag resolves to `APP_COMMIT`, uses that commit as the BuildKit cache key, builds the layered image, verifies the commit again inside the build, and checks that the P3 Python and Desk files are present. To publish to a configured registry, log in first and add `PUSH=1`.

In the ERPNext project's existing environment file, persist these non-secret image variables before deployment:

```text
CUSTOM_IMAGE=skychip/erpnext
CUSTOM_TAG=16.32.0-starcompany-0.1.1
PULL_POLICY=never
```

Do not replace the production environment file with `erpnext-prod.env.example`; merge only the image variables. A versioned tag makes rollback deterministic.

## Deploy Only the ERPNext Project

From the production Compose directory, use the deploy script from the same `frappe_docker` revision:

```bash
chmod +x scripts/deploy-starcompany-image.sh

IMAGE_TAG=16.32.0-starcompany-0.1.1 \
./scripts/deploy-starcompany-image.sh
```

The script is locked to the `erpnext-prod` project. It validates the image and resolved Compose configuration, recreates only `configurator`, `backend`, `frontend`, `websocket`, `queue-short`, `queue-long`, and `scheduler`, then runs site migration and health verification. It does not run `docker compose down` and does not recreate database, Redis, proxy, or services from another Compose project.

If production uses additional Compose overrides, pass the exact existing list:

```bash
COMPOSE_FILES="compose.yaml compose.starcompany.yaml <existing-override.yaml>" \
IMAGE_TAG=16.32.0-starcompany-0.1.1 \
./scripts/deploy-starcompany-image.sh
```

## Install on the Target Site

Run commands from the ERPNext backend container after the new image is running. Replace placeholders with the real Compose project, service, and site values.

```bash
docker compose -p erpnext-prod exec backend bench --site <site-name> install-app starcompany_integration
docker compose -p erpnext-prod exec backend bench --site <site-name> set-config starcompany_api_base_url https://company.skychip.top
docker compose -p erpnext-prod exec backend bench --site <site-name> set-config starcompany_api_timeout_seconds 10
docker compose -p erpnext-prod exec backend bench --site <site-name> set-config starcompany_health_path /api/erpnext/health
docker compose -p erpnext-prod exec backend bench --site <site-name> set-config starcompany_proxy_shared_secret <secret-entered-interactively>
docker compose -p erpnext-prod exec backend bench --site <site-name> migrate
docker compose -p erpnext-prod exec backend bench --site <site-name> clear-cache
```

Set the shared secret interactively and restrict the site configuration file permissions. The secret never belongs in the Git repository, image build arguments, browser code, or application logs.

## Verification

1. Confirm `Starcompany Integration` appears in `bench --site <site-name> list-apps`.
2. Assign the `Starcompany User` role to one non-administrator test user.
3. Confirm that user can open `/app/starcompany-console` and see the identity panel.
4. Confirm a user without that role receives a permission error for the page and for `starcompany_integration.api.proxy.current_user`.
5. Invoke the health check only after Starcompany has deployed its endpoint:

```bash
docker compose -p erpnext-prod exec backend bench --site <site-name> execute starcompany_integration.api.proxy.health_check
```

6. Locate the corresponding `starcompany_proxy` log entry by its `request_id`; it must contain method, path, status, duration, and ERPNext user, but no secret or token.

The integration logger explicitly accepts `INFO` records without changing the global Frappe log level. It writes `starcompany_integration.log` at both bench and site level.

If an emergency file is copied directly into a running container, treat it as a temporary hotfix only. Rebuild the versioned ERPNext image with the same source before the container is recreated; otherwise the container writable-layer change will be lost.

## Rollback

1. Remove the `Starcompany User` role from users to hide the workspace immediately.
2. Restore the recorded previous `CUSTOM_IMAGE` and `CUSTOM_TAG` in the production environment file, then run `scripts/deploy-starcompany-image.sh` with the previous `IMAGE_TAG`.
3. Do not run `uninstall-app` during an incident unless the app's fixtures/data have been reviewed and a database backup is confirmed.

The old ERPNext image and the existing Starcompany Laravel application remain untouched by this rollback.