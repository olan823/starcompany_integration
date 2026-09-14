# Phase 1 Deployment Runbook

## Purpose

Deploy `starcompany_integration` as an application baked into the ERPNext v16 image. This procedure changes only the `erpnext-prod` Compose project. It does not modify, stop, recreate, or attach networks to other Docker projects.

## Preconditions

- The app source has been pushed to a private Git repository reachable by the build host.
- The ERPNext deployment directory, Compose project name, and target site have been confirmed on the server.
- A working backup exists for the ERPNext database and `sites` volume.
- The existing ERPNext image tag and Compose configuration have been recorded for rollback.
- Starcompany has published a dedicated, authenticated read-only health endpoint below `/api/erpnext/`.
- The reverse proxy allows the ERPNext backend container to reach the Starcompany API address.

## Configure the Build

1. Copy `apps.example.json` to the root of the server's `frappe_docker` checkout as `apps.json`.
2. Replace the placeholder URL and branch with the private app repository details. Use BuildKit secret support for any Git token; do not place a token in `apps.json`.
3. Build a new, versioned image. Example:

```bash
docker build --no-cache --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe --build-arg=FRAPPE_BRANCH=version-16 --secret=id=apps_json,src=apps.json --tag=skychip/erpnext:16-starcompany-0.1.0 --file=images/layered/Containerfile .
```

4. In the ERPNext project's environment file, set only these image variables:

```text
CUSTOM_IMAGE=skychip/erpnext
CUSTOM_TAG=16-starcompany-0.1.0
PULL_POLICY=never
```

Do not reuse a generic `latest` tag. A versioned tag makes rollback deterministic.

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

## Rollback

1. Remove the `Starcompany User` role from users to hide the workspace immediately.
2. If required, switch `CUSTOM_IMAGE` and `CUSTOM_TAG` back to the recorded previous image and recreate only the ERPNext project's services.
3. Do not run `uninstall-app` during an incident unless the app's fixtures/data have been reviewed and a database backup is confirmed.

The old ERPNext image and the existing Starcompany Laravel application remain untouched by this rollback.