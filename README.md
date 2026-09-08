# Starcompany Integration

`starcompany_integration` is a Frappe app that provides the native ERPNext Desk entry point and a server-side integration boundary for Starcompany.

## Scope

- The browser calls Frappe only.
- Frappe forwards a restricted read-only health request to Starcompany.
- Starcompany remains the owner of all business data and business rules.
- No client secret, bearer token, or Starcompany database connection is exposed to browser code.

## Site Configuration

Set these values in the target Frappe site configuration. Do not commit secrets in this repository.

```json
{
  "starcompany_api_base_url": "https://company.skychip.top",
  "starcompany_api_timeout_seconds": 10,
  "starcompany_health_path": "/api/erpnext/health",
  "starcompany_proxy_shared_secret": "set-in-site-config"
}
```

`starcompany_health_path` is intentionally blank by default. Starcompany must provide and document the endpoint before the proxy health check is enabled.

## Local Validation

Run this from the app root:

```bash
python -m compileall starcompany_integration
```

## Installation

Build this app into the ERPNext v16 image, then install it only for the intended site:

```bash
bench --site erp.skychip.top install-app starcompany_integration
bench --site erp.skychip.top migrate
bench --site erp.skychip.top clear-cache
```

Use the production deployment runbook before building or recreating any service.