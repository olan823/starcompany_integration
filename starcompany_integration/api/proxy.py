import json
import time
import uuid
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
    frappe.logger("starcompany_integration").info(
        "starcompany_proxy method=%s path=%s status=%s duration_ms=%s user=%s request_id=%s",
        method,
        path,
        status_code,
        duration_ms,
        frappe.session.user,
        request_id,
    )


def request(method, path, payload=None):
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