import json

import frappe


ROLE_NAME = "Starcompany User"
WORKSPACE_NAME = "Starcompany"
PAGE_URL = "/app/starcompany"


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
        frappe.get_doc({"doctype": "Module Def", "module_name": "Starcompany", "app_name": "starcompany_integration"}).insert(
            ignore_permissions=True
        )


def ensure_workspace():
    content = json.dumps(
        [
            {
                "id": "starcompany-shortcuts",
                "type": "shortcut",
                "data": {"shortcut_name": WORKSPACE_NAME, "type": "URL", "url": PAGE_URL},
            },
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
            "shortcuts": [{"label": WORKSPACE_NAME, "type": "URL", "url": PAGE_URL}],
            "roles": [{"role": ROLE_NAME}, {"role": "System Manager"}],
        }
    )

    if workspace.is_new():
        workspace.insert(ignore_permissions=True)
    else:
        workspace.save(ignore_permissions=True)

    frappe.clear_cache(doctype="Workspace")
