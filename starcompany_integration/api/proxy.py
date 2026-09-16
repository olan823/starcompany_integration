import json
import logging
import time
import uuid
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import frappe
from frappe import _


ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE"}
ROLE_NAME = "Starcompany User"


class StarcompanyProxyError(frappe.ValidationError):
    pass


def _require_access():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login is required."), frappe.AuthenticationError)

    roles = frappe.get_roles(frappe.session.user)
    if ROLE_NAME not in roles and "System Manager" not in roles:
        frappe.throw(_("You do not have permission to access Starcompany."), frappe.PermissionError)


def _require_system_manager(action="view"):
    _require_access()
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            _("You do not have permission to {0} authorization pools.").format(action),
            frappe.PermissionError,
        )


def _request_id():
    if getattr(frappe.local, "request", None):
        return frappe.get_request_header("X-Request-ID") or str(uuid.uuid4())
    return str(uuid.uuid4())


def _settings():
    base_url = (frappe.conf.get("starcompany_api_base_url") or "").rstrip("/")
    timeout = int(frappe.conf.get("starcompany_api_timeout_seconds") or 10)
    shared_secret = frappe.conf.get("starcompany_proxy_shared_secret") or ""

    if not base_url:
        frappe.throw(_("Starcompany API base URL is not configured."), StarcompanyProxyError)
    if timeout < 1 or timeout > 60:
        frappe.throw(_("Starcompany API timeout must be between 1 and 60 seconds."), StarcompanyProxyError)

    return base_url, timeout, shared_secret


def _user_context(request_id):
    user = frappe.get_doc("User", frappe.session.user)
    return {
        "request_id": request_id,
        "erpnext_user": user.name,
        "email": user.email or "",
        "full_name": user.full_name or "",
        "roles": frappe.get_roles(user.name),
        "keycloak_sub": user.get("keycloak_subject") or "",
    }


def _log_request(method, path, status_code, duration_ms, request_id):
    logger = frappe.logger("starcompany_integration", allow_site=True)
    logger.setLevel(logging.INFO)
    logger.info(
        "starcompany_proxy method=%s path=%s status=%s duration_ms=%s user=%s request_id=%s",
        method,
        path,
        status_code,
        duration_ms,
        frappe.session.user,
        request_id,
    )


def request(method, path, payload=None, extra_headers=None):
    _require_access()
    method = method.upper()
    if method not in ALLOWED_METHODS:
        frappe.throw(_("Unsupported Starcompany proxy method."), StarcompanyProxyError)
    if not path.startswith("/api/erpnext/") or ".." in path:
        frappe.throw(_("Invalid Starcompany API path."), StarcompanyProxyError)

    base_url, timeout, shared_secret = _settings()
    request_id = _request_id()
    started_at = time.monotonic()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Request-ID": request_id,
        "X-Starcompany-Context": json.dumps(_user_context(request_id), separators=(",", ":")),
    }
    if shared_secret:
        headers["X-Starcompany-Proxy-Secret"] = shared_secret
    if extra_headers:
        headers.update(extra_headers)

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    upstream_request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)

    try:
        with urlopen(upstream_request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            response_data = json.loads(response_body) if response_body else None
            _log_request(method, path, response.status, int((time.monotonic() - started_at) * 1000), request_id)
            return {"data": response_data, "request_id": request_id}
    except HTTPError as error:
        _log_request(method, path, error.code, int((time.monotonic() - started_at) * 1000), request_id)
        frappe.throw(_("Starcompany returned HTTP status {0}.").format(error.code), StarcompanyProxyError)
    except (URLError, TimeoutError) as error:
        _log_request(method, path, 0, int((time.monotonic() - started_at) * 1000), request_id)
        frappe.throw(_("Starcompany is temporarily unavailable."), StarcompanyProxyError)


@frappe.whitelist()
def current_user():
    _require_access()
    request_id = _request_id()
    return {"data": _user_context(request_id), "request_id": request_id}


@frappe.whitelist()
def health_check():
    _require_access()
    health_path = frappe.conf.get("starcompany_health_path") or ""
    if not health_path:
        frappe.throw(_("Starcompany health check is not configured."), StarcompanyProxyError)
    return request("GET", health_path)


@frappe.whitelist()
def authorization_pools(page=1, page_size=20, name=None, platform=None):
    _require_system_manager()

    try:
        page = int(page)
        page_size = int(page_size)
    except (TypeError, ValueError):
        frappe.throw(_("Pagination values must be integers."), StarcompanyProxyError)

    if page < 1 or page_size < 1 or page_size > 100:
        frappe.throw(_("Invalid pagination values."), StarcompanyProxyError)

    params = {"page": page, "page_size": page_size}
    if name:
        params["name"] = str(name)
    if platform not in (None, ""):
        try:
            params["platform"] = int(platform)
        except (TypeError, ValueError):
            frappe.throw(_("Platform must be an integer."), StarcompanyProxyError)

    return request("GET", "/api/erpnext/authorization-pools?" + urlencode(params))


@frappe.whitelist()
def authorization_pool(pool_id):
    _require_system_manager()

    try:
        pool_id = int(pool_id)
    except (TypeError, ValueError):
        frappe.throw(_("Authorization pool ID must be an integer."), StarcompanyProxyError)

    if pool_id < 1:
        frappe.throw(_("Invalid authorization pool ID."), StarcompanyProxyError)

    return request("GET", f"/api/erpnext/authorization-pools/{pool_id}")


@frappe.whitelist()
def update_authorization_pool_threshold(pool_id, threshold, idempotency_key):
    _require_system_manager("update")

    try:
        pool_id = int(pool_id)
        threshold = int(threshold)
    except (TypeError, ValueError):
        frappe.throw(_("Authorization pool ID and threshold must be integers."), StarcompanyProxyError)

    idempotency_key = str(idempotency_key or "").strip()
    if pool_id < 1:
        frappe.throw(_("Invalid authorization pool ID."), StarcompanyProxyError)
    if threshold < 0:
        frappe.throw(_("Threshold cannot be negative."), StarcompanyProxyError)
    if not idempotency_key or len(idempotency_key) > 128:
        frappe.throw(_("Invalid idempotency key."), StarcompanyProxyError)

    return request(
        "PUT",
        f"/api/erpnext/authorization-pools/{pool_id}/threshold",
        {"threshold": threshold},
        {"X-Idempotency-Key": idempotency_key},
    )