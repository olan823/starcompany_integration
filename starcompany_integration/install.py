import json

import frappe


ROLE_NAME = "Starcompany User"
WORKSPACE_NAME = "Starcompany"
SHORTCUTS = [
    ("授权池", "starcompany-console"),
    ("产品管理", "starcompany-products"),
    ("语言包管理", "starcompany-language-packs"),
]
LEGACY_PAGE_NAME = "starcompany"
APP_NAME = "starcompany_integration"
APP_LOGO_URL = "/assets/starcompany_integration/images/starcompany.svg"
APP_HOME = "/app/starcompany"


def after_install():
    ensure_role()
    ensure_module_def()
    ensure_workspace()


def after_uninstall():
    if frappe.db.exists("Workspace", WORKSPACE_NAME):
        frappe.delete_doc("Workspace", WORKSPACE_NAME, force=True, ignore_permissions=True)


def ensure_role():
    if not frappe.db.exists("Role", ROLE_NAME):
        frappe.get_doc({"doctype": "Role", "role_name": ROLE_NAME}).insert(ignore_permissions=True)


def ensure_module_def():
    if not frappe.db.exists("Module Def", "Starcompany"):
        frappe.get_doc({"doctype": "Module Def", "module_name": "Starcompany", "app_name": APP_NAME}).insert(
            ignore_permissions=True
        )


def ensure_workspace():
    ensure_desktop_icon()

    if frappe.db.exists("Page", LEGACY_PAGE_NAME):
        frappe.delete_doc("Page", LEGACY_PAGE_NAME, force=True, ignore_permissions=True)

    content = json.dumps(
        [
            {
                "id": f"starcompany-shortcut-{index}",
                "type": "shortcut",
                "data": {"shortcut_name": label},
            }
            for index, (label, page_name) in enumerate(SHORTCUTS, start=1)
        ]
    )
    workspace = (
        frappe.get_doc("Workspace", WORKSPACE_NAME)
        if frappe.db.exists("Workspace", WORKSPACE_NAME)
        else frappe.new_doc("Workspace")
    )
    workspace.update(
        {
            "label": WORKSPACE_NAME,
            "title": WORKSPACE_NAME,
            "module": "Starcompany",
            "icon": "organization",
            "public": 1,
            "is_hidden": 0,
            "content": content,
            "shortcuts": [
                {"label": label, "type": "Page", "link_to": page_name}
                for label, page_name in SHORTCUTS
            ],
            "roles": [{"role": ROLE_NAME}, {"role": "System Manager"}],
        }
    )

    if workspace.is_new():
        workspace.insert(ignore_permissions=True)
    else:
        workspace.save(ignore_permissions=True)

    frappe.clear_cache(doctype="Workspace")


def ensure_desktop_icon():
    app_icon_names = frappe.get_all(
        "Desktop Icon",
        filters={"app": APP_NAME, "icon_type": "App"},
        pluck="name",
        order_by="creation asc",
    )
    matching_icon_names = frappe.get_all(
        "Desktop Icon", filters={"label": WORKSPACE_NAME}, pluck="name", order_by="creation asc"
    )
    icon_name = app_icon_names[0] if app_icon_names else None
    icon_name = icon_name or (matching_icon_names[0] if matching_icon_names else None)

    for duplicate_name in dict.fromkeys([*app_icon_names, *matching_icon_names]):
        if duplicate_name != icon_name:
            frappe.delete_doc("Desktop Icon", duplicate_name, force=True, ignore_permissions=True)

    icon = (
        frappe.get_doc("Desktop Icon", icon_name) if icon_name else frappe.new_doc("Desktop Icon")
    )
    icon.update(
        {
            "label": WORKSPACE_NAME,
            "link_type": "External",
            "icon_type": "App",
            "app": APP_NAME,
            "link": APP_HOME,
            "logo_url": APP_LOGO_URL,
        }
    )

    if icon.is_new():
        icon.insert(ignore_permissions=True)
    else:
        icon.save(ignore_permissions=True)

    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")

