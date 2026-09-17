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
