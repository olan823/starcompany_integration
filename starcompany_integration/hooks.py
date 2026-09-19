app_name = "starcompany_integration"
app_title = "Starcompany Integration"
app_publisher = "Skychip"
app_description = "Native ERPNext integration boundary for Starcompany"
app_email = ""
app_license = "MIT"
app_logo_url = "/assets/starcompany_integration/images/starcompany.svg"
app_home = "/app/starcompany"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": "Starcompany",
		"route": app_home,
	}
]

after_install = "starcompany_integration.install.after_install"
after_migrate = "starcompany_integration.install.ensure_workspace"
after_uninstall = "starcompany_integration.install.after_uninstall"
