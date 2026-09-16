frappe.pages["starcompany-console"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Starcompany"),
		single_column: true,
	});

	const content = $('<div class="starcompany-integration"></div>').appendTo(page.main);
	let currentPage = 1;

	function renderError() {
		content.html('<div class="text-danger">' + __("Unable to load authorization pools.") + "</div>");
	}

	function showPool(poolId) {
		frappe.call({
			method: "starcompany_integration.api.proxy.authorization_pool",
			args: { pool_id: poolId },
		}).then((response) => {
			const pool = response.message.data.data;
			const escape = frappe.utils.escape_html;
			let idempotencyKey = null;
			const dialog = new frappe.ui.Dialog({
				title: escape(pool.name),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "details",
						options:
							'<table class="table table-bordered">' +
							'<tbody><tr><th>' + __("Platform") + '</th><td>' + escape(pool.platform_name) + "</td></tr>" +
							'<tr><th>' + __("Supported models") + '</th><td>' + escape((pool.supported_models || []).join(", ")) + "</td></tr>" +
							'<tr><th>' + __("Used / total") + '</th><td>' + pool.used_count + " / " + pool.total_count + "</td></tr>" +
							'<tr><th>' + __("Created at") + '</th><td>' + escape(pool.created_at || "") + "</td></tr></tbody></table>",
					},
					{
						fieldtype: "Int",
						fieldname: "threshold",
						label: __("Threshold"),
						reqd: 1,
						default: pool.threshold,
					},
				],
				primary_action_label: __("Update threshold"),
				primary_action(values) {
					if (values.threshold < 0) {
						frappe.msgprint(__("Threshold cannot be negative."));
						return;
					}

					frappe.confirm(
						__("Change the threshold from {0} to {1}?", [pool.threshold, values.threshold]),
						() => {
							idempotencyKey = idempotencyKey || (
								window.crypto && window.crypto.randomUUID
									? window.crypto.randomUUID()
									: `${Date.now()}-${Math.random().toString(36).slice(2)}`
							);
							const primaryButton = dialog.get_primary_btn();
							primaryButton.prop("disabled", true);

							frappe.call({
								method: "starcompany_integration.api.proxy.update_authorization_pool_threshold",
								args: {
									pool_id: pool.id,
									threshold: values.threshold,
									idempotency_key: idempotencyKey,
								},
							}).then((updateResponse) => {
								const result = updateResponse.message.data.data;
								dialog.hide();
								frappe.show_alert({
									message: result.applied ? __("Threshold updated.") : __("Threshold is unchanged."),
									indicator: "green",
								});
								loadPools(currentPage);
							}).catch(() => {
								frappe.msgprint(__("Unable to update the threshold. You can retry this dialog safely."));
							}).finally(() => primaryButton.prop("disabled", false));
						},
					);
				},
			});
			dialog.show();
		}).catch(() => frappe.msgprint(__("Unable to load authorization pool details.")));
	}

	function loadPools(pageNumber) {
		const search = content.find(".starcompany-pool-search").val() || "";
		const platform = content.find(".starcompany-pool-platform").val();
		content.find(".starcompany-pool-results").html('<div class="text-muted">' + __("Loading...") + "</div>");

		frappe.call({
			method: "starcompany_integration.api.proxy.authorization_pools",
			args: { page: pageNumber, page_size: 20, name: search, platform },
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
					'<td><button class="btn btn-default btn-xs starcompany-pool-detail" data-pool-id="' + pool.id + '">' + __("Details") + "</button></td>" +
					"</tr>"
			)).join("") || '<tr><td colspan="6" class="text-muted text-center">' + __("No authorization pools found.") + "</td></tr>";

			content.find(".starcompany-pool-results").html(
				'<table class="table table-bordered">' +
					"<thead><tr><th>" + __("Name") + "</th><th>" + __("Platform") + "</th><th>" + __("Supported models") + "</th><th class='text-right'>" + __("Used / total") + "</th><th class='text-right'>" + __("Threshold") + "</th><th>" + __("Actions") + "</th></tr></thead>" +
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
			'<div class="flex mb-3"><input class="form-control starcompany-pool-search" placeholder="' + __("Search by name") + '">' +
			'<select class="form-control ml-2 starcompany-pool-platform"><option value="">' + __("All platforms") + '</option><option value="0">' + __("Xing Lock") + '</option><option value="1">' + __("Tuya") + '</option><option value="2">' + __("Tuya Intercom") + '</option><option value="3">' + __("Tencent Cloud") + '</option></select>' +
			'<button class="btn btn-primary ml-2 starcompany-pool-submit">' + __("Search") + "</button></div>" +
			'<div class="starcompany-pool-results"></div></div></div></div>'
		);
		content.on("click", ".starcompany-pool-submit", () => loadPools(1));
		content.on("click", ".starcompany-pool-detail", (event) => showPool($(event.currentTarget).data("pool-id")));
		content.on("click", ".starcompany-pool-previous", () => loadPools(currentPage - 1));
		content.on("click", ".starcompany-pool-next", () => loadPools(currentPage + 1));
		content.on("keydown", ".starcompany-pool-search", (event) => {
			if (event.key === "Enter") loadPools(1);
		});
		loadPools(1);
	}).catch(renderError);
};