frappe.pages["starcompany"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Starcompany"),
		single_column: true,
	});

	const content = $('<div class="starcompany-integration"></div>').appendTo(page.body);
	let currentPage = 1;

	function renderError() {
		content.html('<div class="text-danger">' + __("Unable to load authorization pools.") + "</div>");
	}

	function loadPools(pageNumber) {
		const search = content.find(".starcompany-pool-search").val() || "";
		content.find(".starcompany-pool-results").html('<div class="text-muted">' + __("Loading...") + "</div>");

		frappe.call({
			method: "starcompany_integration.api.proxy.authorization_pools",
			args: { page: pageNumber, page_size: 20, name: search },
		}).then((response) => {
			const payload = response.message.data.data;
			const pools = payload.items;
			const pagination = payload.pagination;
			currentPage = pagination.page;
			const rows = pools.map((pool) => (
				"<tr>" +
				"<td>" + frappe.utils.escape_html(pool.name) + "</td>" +
				"<td>" + frappe.utils.escape_html(pool.platform_name) + "</td>" +
				"<td>" + frappe.utils.escape_html((pool.supported_models || []).join(", ")) + "</td>" +
				"<td class='text-right'>" + pool.used_count + " / " + pool.total_count + "</td>" +
				"<td class='text-right'>" + pool.threshold + "</td>" +
				"</tr>"
			)).join("") || '<tr><td colspan="5" class="text-muted text-center">' + __("No authorization pools found.") + "</td></tr>";

			content.find(".starcompany-pool-results").html(
				'<table class="table table-bordered">' +
				"<thead><tr><th>" + __("Name") + "</th><th>" + __("Platform") + "</th><th>" + __("Supported models") + "</th><th class='text-right'>" + __("Used / total") + "</th><th class='text-right'>" + __("Threshold") + "</th></tr></thead>" +
				"<tbody>" + rows + "</tbody></table>" +
				'<div class="flex justify-between align-center">' +
				'<span class="text-muted">' + __("{0} records", [pagination.total]) + "</span>" +
				'<div><button class="btn btn-default btn-sm starcompany-pool-previous" ' + (pagination.page <= 1 ? "disabled" : "") + ">" + __("Previous") + "</button> " +
				'<button class="btn btn-default btn-sm starcompany-pool-next" ' + (pagination.page >= pagination.last_page ? "disabled" : "") + ">" + __("Next") + "</button></div></div>"
			);
		}).catch(renderError);
	}

	frappe.call({ method: "starcompany_integration.api.proxy.current_user" }).then((response) => {
		const user = response.message.data;
		content.html(
			'<div class="form-layout"><div class="form-page">' +
			'<div class="form-dashboard-section"><div class="section-head">' + __("Identity") + "</div>" +
			'<div class="text-muted">' + frappe.utils.escape_html(user.full_name || user.email) + "</div></div>" +
			'<div class="form-dashboard-section"><div class="section-head">' + __("Authorization pools") + "</div>" +
			'<div class="flex mb-3"><input class="form-control starcompany-pool-search" placeholder="' + __("Search by name") + '"><button class="btn btn-primary ml-2 starcompany-pool-submit">' + __("Search") + "</button></div>" +
			       '<div class="starcompany-pool-results"></div></div></div></div>'
		);
		content.on("click", ".starcompany-pool-submit", () => loadPools(1));
		content.on("click", ".starcompany-pool-previous", () => loadPools(currentPage - 1));
		content.on("click", ".starcompany-pool-next", () => loadPools(currentPage + 1));
		content.on("keydown", ".starcompany-pool-search", (event) => {
			if (event.key === "Enter") loadPools(1);
		});
		loadPools(1);
	}).catch(renderError);
};