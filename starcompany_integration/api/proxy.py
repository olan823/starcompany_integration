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
            _("You do not have permission to {0} Starcompany resources.").format(action),
            frappe.PermissionError,
        )


def _positive_int(value, label):
    try:
        value = int(value)
    except (TypeError, ValueError):
        frappe.throw(_("{0} must be an integer.").format(label), StarcompanyProxyError)
    if value < 1:
        frappe.throw(_("Invalid {0}.").format(label), StarcompanyProxyError)
    return value


def _json_list(value, label):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            frappe.throw(_("{0} must be a JSON list.").format(label), StarcompanyProxyError)
    if not isinstance(value, list) or not value:
        frappe.throw(_("{0} must not be empty.").format(label), StarcompanyProxyError)
    return value


def _write_headers(idempotency_key):
    idempotency_key = str(idempotency_key or "").strip()
    if not idempotency_key or len(idempotency_key) > 128:
        frappe.throw(_("Invalid idempotency key."), StarcompanyProxyError)
    return {"X-Idempotency-Key": idempotency_key}


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
def dashboard_stats():
    _require_access()
    return request("GET", "/api/erpnext/dashboard-stats")


@frappe.whitelist()
def iot_card(card_number):
    _require_access()
    card_number = str(card_number or "").strip()
    if not card_number or len(card_number) > 100:
        frappe.throw(_("IoT card number must contain 1 to 100 characters."), StarcompanyProxyError)
    return request("POST", "/api/erpnext/iot-card/query", {"card_number": card_number})


@frappe.whitelist()
def authorization_pools(page=1, page_size=20, name=None, platform=None):
    _require_access()

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
    _require_access()

    try:
        pool_id = int(pool_id)
    except (TypeError, ValueError):
        frappe.throw(_("Authorization pool ID must be an integer."), StarcompanyProxyError)

    if pool_id < 1:
        frappe.throw(_("Invalid authorization pool ID."), StarcompanyProxyError)

    return request("GET", f"/api/erpnext/authorization-pools/{pool_id}")


@frappe.whitelist()
def authorization_codes(pool_id, page=1, page_size=20, code=None, status=None):
    _require_access()
    pool_id = _positive_int(pool_id, _("authorization pool ID"))
    page = _positive_int(page, _("page"))
    page_size = _positive_int(page_size, _("page size"))
    if page_size > 100:
        frappe.throw(_("Page size cannot exceed 100."), StarcompanyProxyError)

    params = {"page": page, "page_size": page_size}
    if code:
        code = str(code).strip()
        if len(code) > 255:
            frappe.throw(_("Authorization code search cannot exceed 255 characters."), StarcompanyProxyError)
        params["code"] = code
    if status not in (None, ""):
        try:
            status = int(status)
        except (TypeError, ValueError):
            frappe.throw(_("Authorization code status must be an integer."), StarcompanyProxyError)
        if status not in (0, 1):
            frappe.throw(_("Invalid authorization code status."), StarcompanyProxyError)
        params["status"] = status

    return request("GET", f"/api/erpnext/authorization-pools/{pool_id}/codes?" + urlencode(params))


@frappe.whitelist()
def add_authorization_codes(pool_id, codes, idempotency_key):
    _require_system_manager("add authorization codes")
    pool_id = _positive_int(pool_id, _("authorization pool ID"))
    codes = _json_list(codes, _("Authorization codes"))
    if len(codes) > 500:
        frappe.throw(_("No more than 500 authorization codes can be added at once."), StarcompanyProxyError)

    normalized_codes = []
    for code in codes:
        if not isinstance(code, str):
            frappe.throw(_("Each authorization code must be text."), StarcompanyProxyError)
        code = code.strip()
        if not code or len(code) > 255:
            frappe.throw(_("Each authorization code must contain 1 to 255 characters."), StarcompanyProxyError)
        normalized_codes.append(code)

    return request(
        "POST",
        f"/api/erpnext/authorization-pools/{pool_id}/codes",
        {"codes": normalized_codes},
        _write_headers(idempotency_key),
    )


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


@frappe.whitelist()
def products(page=1, page_size=20, name=None):
    _require_access()
    page = _positive_int(page, _("page"))
    page_size = _positive_int(page_size, _("page size"))
    if page_size > 100:
        frappe.throw(_("Page size cannot exceed 100."), StarcompanyProxyError)
    params = {"page": page, "page_size": page_size}
    if name:
        params["name"] = str(name)
    return request("GET", "/api/erpnext/products?" + urlencode(params))


@frappe.whitelist()
def product(product_id):
    _require_access()
    return request("GET", f"/api/erpnext/products/{_positive_int(product_id, _('product ID'))}")


@frappe.whitelist()
def save_product(name, vendor, models, image="", manual="", product_id=None, idempotency_key=None):
    _require_system_manager("manage products")
    payload = {
        "name": str(name or "").strip(),
        "vendor": str(vendor or "").strip(),
        "models": _json_list(models, _("Models")),
        "image": str(image or "").strip(),
        "manual": str(manual or "").strip(),
    }
    headers = _write_headers(idempotency_key)
    if product_id in (None, ""):
        return request("POST", "/api/erpnext/products", payload, headers)
    product_id = _positive_int(product_id, _("product ID"))
    return request("PUT", f"/api/erpnext/products/{product_id}", payload, headers)


@frappe.whitelist()
def delete_product(product_id, idempotency_key):
    _require_system_manager("delete products")
    product_id = _positive_int(product_id, _("product ID"))
    return request("DELETE", f"/api/erpnext/products/{product_id}", {}, _write_headers(idempotency_key))


@frappe.whitelist()
def voice_pack_structures(page=1, page_size=20, name=None):
    _require_access()
    page = _positive_int(page, _("page"))
    page_size = _positive_int(page_size, _("page size"))
    if page_size > 100:
        frappe.throw(_("Page size cannot exceed 100."), StarcompanyProxyError)
    params = {"page": page, "page_size": page_size}
    if name:
        params["name"] = str(name)
    return request("GET", "/api/erpnext/voice-pack-structures?" + urlencode(params))


@frappe.whitelist()
def voice_pack_structure(structure_id):
    _require_access()
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("GET", f"/api/erpnext/voice-pack-structures/{structure_id}")


@frappe.whitelist()
def save_voice_pack_structure(name, product_ids, chip_type=None, structure_id=None, idempotency_key=None):
    _require_system_manager("manage voice pack structures")
    payload = {"name": str(name or "").strip(), "product_ids": _json_list(product_ids, _("Products"))}
    headers = _write_headers(idempotency_key)
    if structure_id in (None, ""):
        payload["chip_type"] = str(chip_type or "").strip()
        return request("POST", "/api/erpnext/voice-pack-structures", payload, headers)
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("PUT", f"/api/erpnext/voice-pack-structures/{structure_id}", payload, headers)


@frappe.whitelist()
def delete_voice_pack_structure(structure_id, idempotency_key):
    _require_system_manager("delete voice pack structures")
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("DELETE", f"/api/erpnext/voice-pack-structures/{structure_id}", {}, _write_headers(idempotency_key))


@frappe.whitelist()
def voice_pack_languages(structure_id, lang=None):
    _require_access()
    structure_id = _positive_int(structure_id, _("structure ID"))
    params = urlencode({"lang": str(lang)}) if lang else ""
    suffix = f"?{params}" if params else ""
    return request("GET", f"/api/erpnext/voice-pack-structures/{structure_id}/languages{suffix}")


@frappe.whitelist()
def voice_options(structure_id):
    _require_access()
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("GET", f"/api/erpnext/voice-pack-structures/{structure_id}/voice-options")


@frappe.whitelist()
def add_voice_pack_language(structure_id, lang, idempotency_key):
    _require_system_manager("add voice pack languages")
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("POST", f"/api/erpnext/voice-pack-structures/{structure_id}/languages", {"lang": str(lang)}, _write_headers(idempotency_key))


@frappe.whitelist()
def delete_voice_pack_language(language_id, idempotency_key):
    _require_system_manager("delete voice pack languages")
    language_id = _positive_int(language_id, _("language ID"))
    return request("DELETE", f"/api/erpnext/voice-pack-languages/{language_id}", {}, _write_headers(idempotency_key))


@frappe.whitelist()
def add_voice_pack_timbres(language_id, timbres, idempotency_key):
    _require_system_manager("add voice pack timbres")
    language_id = _positive_int(language_id, _("language ID"))
    return request("POST", f"/api/erpnext/voice-pack-languages/{language_id}/timbres", {"timbres": _json_list(timbres, _("Timbres"))}, _write_headers(idempotency_key))


@frappe.whitelist()
def delete_voice_pack_timbre(timbre_id, idempotency_key):
    _require_system_manager("delete voice pack timbres")
    timbre_id = _positive_int(timbre_id, _("timbre ID"))
    return request("DELETE", f"/api/erpnext/voice-pack-timbres/{timbre_id}", {}, _write_headers(idempotency_key))


@frappe.whitelist()
def voice_pack_items(timbre_id):
    _require_access()
    timbre_id = _positive_int(timbre_id, _("timbre ID"))
    return request("GET", f"/api/erpnext/voice-pack-timbres/{timbre_id}/items")


@frappe.whitelist()
def generate_voice_pack_item(item_id, idempotency_key):
    _require_system_manager("generate voice")
    item_id = _positive_int(item_id, _("item ID"))
    return request("POST", f"/api/erpnext/voice-pack-items/{item_id}/generate", {}, _write_headers(idempotency_key))


@frappe.whitelist()
def generate_voice_pack_structure(structure_id, idempotency_key):
    _require_system_manager("generate voice")
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("POST", f"/api/erpnext/voice-pack-structures/{structure_id}/generate", {}, _write_headers(idempotency_key))


@frappe.whitelist()
def voice_pack_generation(structure_id):
    _require_access()
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("GET", f"/api/erpnext/voice-pack-structures/{structure_id}/generation")


@frappe.whitelist()
def sync_voice_pack_structure(structure_id, idempotency_key):
    _require_system_manager("sync voice packs")
    structure_id = _positive_int(structure_id, _("structure ID"))
    return request("POST", f"/api/erpnext/voice-pack-structures/{structure_id}/sync", {}, _write_headers(idempotency_key))