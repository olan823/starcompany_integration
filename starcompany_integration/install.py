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
DASHBOARD_BLOCK_NAME = "Starcompany Dashboard Statistics"
DASHBOARD_HTML = """
<section class="dashboard" aria-labelledby="dashboard-title">
    <div class="dashboard__heading">
        <div>
            <p class="dashboard__eyebrow">实时数据</p>
            <h2 id="dashboard-title">星启运营概览</h2>
        </div>
        <button class="dashboard__refresh" type="button">刷新</button>
    </div>
    <div class="dashboard__metrics" aria-live="polite">
        <a class="metric metric--authorization" href="/app/starcompany-console">
            <span class="metric__label">授权码 Used / Total</span>
            <strong class="metric__value" data-stat="authorization">-- / --</strong>
            <span class="metric__hint">查看授权池</span>
        </a>
        <a class="metric metric--language" href="/app/starcompany-language-packs">
            <span class="metric__label">多国语音包国家</span>
            <strong class="metric__value" data-stat="language_count">--</strong>
            <span class="metric__hint">查看语言包</span>
        </a>
        <a class="metric metric--generated" href="/app/starcompany-language-packs">
            <span class="metric__label">语音已生成</span>
            <strong class="metric__value" data-stat="voice_generated">--</strong>
            <span class="metric__hint">生成结果</span>
        </a>
        <a class="metric metric--pending" href="/app/starcompany-language-packs">
            <span class="metric__label">语音未生成</span>
            <strong class="metric__value" data-stat="voice_pending">--</strong>
            <span class="metric__hint">待处理项目</span>
        </a>
    </div>
    <div class="dashboard__error" role="alert" hidden>
        <span>统计数据暂时无法加载。</span>
        <button type="button" data-action="retry">重试</button>
    </div>
</section>
"""
DASHBOARD_STYLE = """
:host { display: block; }
.dashboard { color: var(--text-color); padding: 4px 0 12px; }
.dashboard__heading { align-items: end; display: flex; justify-content: space-between; margin-bottom: 16px; }
.dashboard__eyebrow { color: var(--text-muted); font-size: 12px; font-weight: 600; margin: 0 0 4px; }
.dashboard h2 { font-size: 20px; font-weight: 650; line-height: 1.3; margin: 0; }
.dashboard__refresh, .dashboard__error button { background: var(--control-bg); border: 1px solid var(--border-color); border-radius: 6px; color: var(--text-color); cursor: pointer; min-height: 32px; padding: 5px 12px; }
.dashboard__refresh:disabled { cursor: wait; opacity: .6; }
.dashboard__metrics { display: grid; gap: 12px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.metric { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; color: inherit; display: flex; flex-direction: column; min-height: 132px; padding: 18px; position: relative; text-decoration: none; }
.metric::before { background: var(--accent); content: ""; height: 3px; left: 18px; position: absolute; right: 18px; top: 0; }
.metric:hover { border-color: var(--accent); color: inherit; text-decoration: none; }
.metric--authorization { --accent: #2563eb; }
.metric--language { --accent: #0891b2; }
.metric--generated { --accent: #16a34a; }
.metric--pending { --accent: #d97706; }
.metric__label { color: var(--text-muted); font-size: 13px; }
.metric__value { font-size: 28px; font-weight: 700; line-height: 1.2; margin-top: 14px; overflow-wrap: anywhere; }
.metric__hint { color: var(--text-muted); font-size: 12px; margin-top: auto; padding-top: 10px; }
.dashboard__error { align-items: center; background: var(--subtle-fg); border: 1px solid var(--border-color); border-radius: 8px; display: flex; gap: 12px; justify-content: space-between; margin-top: 12px; padding: 12px 14px; }
.dashboard__error[hidden] { display: none; }
@media (max-width: 900px) { .dashboard__metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 520px) { .dashboard__heading { align-items: center; } .dashboard__metrics { grid-template-columns: 1fr; } .metric { min-height: 118px; } }
"""
DASHBOARD_SCRIPT = """
const refresh_button = root_element.querySelector(".dashboard__refresh");
const retry_button = root_element.querySelector('[data-action="retry"]');
const error_box = root_element.querySelector(".dashboard__error");
const formatter = new Intl.NumberFormat();

const set_value = (name, value) => {
    root_element.querySelector(`[data-stat="${name}"]`).textContent = value;
};

const load_stats = async () => {
    refresh_button.disabled = true;
    error_box.hidden = true;
    try {
        const response = await frappe.call({
            method: "starcompany_integration.api.proxy.dashboard_stats",
        });
        const stats = response.message.data.data;
        set_value("authorization", `${formatter.format(stats.authorization_used)} / ${formatter.format(stats.authorization_total)}`);
        set_value("language_count", formatter.format(stats.language_count));
        set_value("voice_generated", formatter.format(stats.voice_generated));
        set_value("voice_pending", formatter.format(stats.voice_pending));
    } catch (error) {
        error_box.hidden = false;
    } finally {
        refresh_button.disabled = false;
    }
};

refresh_button.addEventListener("click", load_stats);
retry_button.addEventListener("click", load_stats);
load_stats();
"""


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
    ensure_dashboard_block()

    if frappe.db.exists("Page", LEGACY_PAGE_NAME):
        frappe.delete_doc("Page", LEGACY_PAGE_NAME, force=True, ignore_permissions=True)

    content = json.dumps(
        [{
            "id": "starcompany-dashboard-statistics",
            "type": "custom_block",
            "data": {"custom_block_name": DASHBOARD_BLOCK_NAME, "col": 12},
        }] + [
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
            "custom_blocks": [
                {"label": DASHBOARD_BLOCK_NAME, "custom_block_name": DASHBOARD_BLOCK_NAME}
            ],
            "roles": [{"role": ROLE_NAME}, {"role": "System Manager"}],
        }
    )

    if workspace.is_new():
        workspace.insert(ignore_permissions=True)
    else:
        workspace.save(ignore_permissions=True)

    ensure_custom_workspace_dashboard_block()
    ensure_sidebar()
    frappe.clear_cache(doctype="Workspace")


def ensure_custom_workspace_dashboard_block():
    customization_name = frappe.db.exists("Custom Workspace", {"workspace": WORKSPACE_NAME})
    if not customization_name:
        return

    customization = frappe.get_doc("Custom Workspace", customization_name)
    if not customization.content:
        return

    content = frappe.parse_json(customization.content)
    if any(
        block.get("type") == "custom_block"
        and block.get("data", {}).get("custom_block_name") == DASHBOARD_BLOCK_NAME
        for block in content
    ):
        return

    content.insert(
        0,
        {
            "id": "starcompany-dashboard-statistics",
            "type": "custom_block",
            "data": {"custom_block_name": DASHBOARD_BLOCK_NAME, "col": 12},
        },
    )
    customization.content = json.dumps(content)
    customization.save(ignore_permissions=True)


def ensure_dashboard_block():
    block = (
        frappe.get_doc("Custom HTML Block", DASHBOARD_BLOCK_NAME)
        if frappe.db.exists("Custom HTML Block", DASHBOARD_BLOCK_NAME)
        else frappe.get_doc({"doctype": "Custom HTML Block", "name": DASHBOARD_BLOCK_NAME})
    )
    block.update(
        {
            "private": 0,
            "html": DASHBOARD_HTML,
            "style": DASHBOARD_STYLE,
            "script": DASHBOARD_SCRIPT,
            "roles": [{"role": ROLE_NAME}, {"role": "System Manager"}],
        }
    )
    if block.is_new():
        block.insert(ignore_permissions=True)
    else:
        block.save(ignore_permissions=True)


def ensure_sidebar():
    sidebar_name = frappe.db.exists("Sidebar", {"module": WORKSPACE_NAME})
    sidebar = (
        frappe.get_doc("Sidebar", sidebar_name) if sidebar_name else frappe.new_doc("Sidebar")
    )
    sidebar.update(
        {
            "module": WORKSPACE_NAME,
            "title": WORKSPACE_NAME,
            "header_icon": "organization",
            "standard": 0,
        }
    )
    sidebar.set("items", [])
    sidebar.append(
        "items",
        {
            "type": "Link",
            "label": "Home",
            "link_type": "Workspace",
            "link_to": WORKSPACE_NAME,
        },
    )
    for label, page_name in SHORTCUTS:
        sidebar.append(
            "items",
            {
                "type": "Link",
                "label": label,
                "link_type": "Page",
                "link_to": page_name,
            },
        )

    if sidebar.is_new():
        sidebar.insert(ignore_permissions=True)
    else:
        sidebar.save(ignore_permissions=True)


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
            "link_to": None,
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

