frappe.pages["starcompany"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Starcompany"),
		single_column: true,
	});

	const content = $('<div class="starcompany-integration"></div>').appendTo(page.body);
	content.html('<div class="text-muted">' + __("Loading...") + "</div>");

	frappe.call({
		method: "starcompany_integration.api.proxy.current_user",
	}).then((response) => {
		const user = response.message.data;
		content.html(
			'<div class="form-layout">' +
				'<div class="form-page">' +
					'<div class="form-dashboard-section">' +
						'<div class="section-head">' + __("Identity") + "</div>" +
						'<div class="text-muted">' + frappe.utils.escape_html(user.full_name || user.email) + "</div>" +
					"</div>" +
				"</div>" +
			"</div>"
		);
	}).catch(() => {
		content.html('<div class="text-danger">' + __("Unable to load Starcompany identity.") + "</div>");
	});
};