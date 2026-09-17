frappe.pages["starcompany-products"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Starcompany"),
		single_column: true,
	});
	const content = $('<div class="starcompany-products"></div>').appendTo(page.main);
	let currentPage = 1;
	let canWrite = false;

	function idempotencyKey() {
		return window.crypto && window.crypto.randomUUID
			? window.crypto.randomUUID()
			: `${Date.now()}-${Math.random().toString(36).slice(2)}`;
	}

	function call(method, args = {}) {
		return frappe.call({ method: `starcompany_integration.api.proxy.${method}`, args });
	}

	function upstream(response) {
		return response.message.data.data;
	}

	function showError(message) {
		frappe.msgprint(message);
	}

	function productDialog(product = null) {
		let operationKey = null;
		const dialog = new frappe.ui.Dialog({
			title: product ? __("Edit product") : __("New product"),
			fields: [
				{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1, default: product?.name || "" },
				{ fieldtype: "Data", fieldname: "vendor", label: __("Vendor"), reqd: 1, default: product?.vendor || "" },
				{ fieldtype: "Small Text", fieldname: "models", label: __("Models"), reqd: 1, default: (product?.models || []).join("\n") },
				{ fieldtype: "Data", fieldname: "image", label: __("Image URL"), default: product?.image || "" },
				{ fieldtype: "Data", fieldname: "manual", label: __("Manual URL"), default: product?.manual || "" },
			],
			primary_action_label: __("Save"),
			primary_action(values) {
				const models = values.models.split(/[\n,]+/).map((value) => value.trim()).filter(Boolean);
				if (!models.length) {
					showError(__("Enter at least one model."));
					return;
				}
				operationKey = operationKey || idempotencyKey();
				const button = dialog.get_primary_btn().prop("disabled", true);
				call("save_product", {
					product_id: product?.id || null,
					name: values.name,
					vendor: values.vendor,
					models: JSON.stringify(models),
					image: values.image || "",
					manual: values.manual || "",
					idempotency_key: operationKey,
				}).then(() => {
					dialog.hide();
					frappe.show_alert({ message: __("Product saved."), indicator: "green" });
					loadProducts(currentPage);
				}).catch(() => showError(__("Unable to save the product. You can retry safely.")))
					.finally(() => button.prop("disabled", false));
			},
		});
		dialog.show();
	}

	function showProduct(productId) {
		call("product", { product_id: productId }).then((response) => {
			const product = upstream(response);
			const escape = frappe.utils.escape_html;
			const dialog = new frappe.ui.Dialog({
				title: escape(product.name),
				fields: [{
					fieldtype: "HTML",
					options: '<table class="table table-bordered"><tbody>' +
						`<tr><th>${__("Vendor")}</th><td>${escape(product.vendor || "")}</td></tr>` +
						`<tr><th>${__("Models")}</th><td>${escape((product.models || []).join(", "))}</td></tr>` +
						`<tr><th>${__("Image URL")}</th><td>${escape(product.image || "")}</td></tr>` +
						`<tr><th>${__("Manual URL")}</th><td>${escape(product.manual || "")}</td></tr>` +
						"</tbody></table>",
				}],
			});
			if (canWrite) {
				dialog.set_secondary_action_label(__("Edit"));
				dialog.set_secondary_action(() => {
					dialog.hide();
					productDialog(product);
				});
			}
			dialog.show();
		}).catch(() => showError(__("Unable to load product details.")));
	}

	function deleteProduct(productId, productName) {
		frappe.confirm(__("Delete product {0}?", [frappe.utils.escape_html(productName)]), () => {
			const key = idempotencyKey();
			call("delete_product", { product_id: productId, idempotency_key: key })
				.then(() => {
					frappe.show_alert({ message: __("Product deleted."), indicator: "green" });
					loadProducts(currentPage);
				})
				.catch(() => showError(__("Unable to delete this product.")));
		});
	}

	function loadProducts(pageNumber) {
		const name = content.find(".starcompany-product-search").val() || "";
		content.find(".starcompany-product-results").html(`<div class="text-muted">${__("Loading...")}</div>`);
		call("products", { page: pageNumber, page_size: 20, name }).then((response) => {
			const payload = upstream(response);
			currentPage = payload.pagination.page;
			const escape = frappe.utils.escape_html;
			const rows = payload.items.map((product) => {
				const actions = `<button class="btn btn-default btn-xs product-view" data-id="${product.id}">${__("Details")}</button>` +
					(canWrite ? ` <button class="btn btn-danger btn-xs product-delete" data-id="${product.id}" data-name="${escape(product.name)}">${__("Delete")}</button>` : "");
				return `<tr><td>${escape(product.name)}</td><td>${escape(product.vendor || "")}</td>` +
					`<td>${escape((product.models || []).join(", "))}</td><td>${actions}</td></tr>`;
			}).join("") || `<tr><td colspan="4" class="text-muted text-center">${__("No products found.")}</td></tr>`;
			content.find(".starcompany-product-results").html(
				'<table class="table table-bordered"><thead><tr>' +
				`<th>${__("Name")}</th><th>${__("Vendor")}</th><th>${__("Models")}</th><th>${__("Actions")}</th>` +
				`</tr></thead><tbody>${rows}</tbody></table>` +
				'<div class="flex justify-between align-center">' +
				`<span class="text-muted">${__("{0} records", [payload.pagination.total])}</span>` +
				`<div><button class="btn btn-default btn-sm product-previous" ${currentPage <= 1 ? "disabled" : ""}>${__("Previous")}</button> ` +
				`<button class="btn btn-default btn-sm product-next" ${currentPage >= payload.pagination.last_page ? "disabled" : ""}>${__("Next")}</button></div></div>`
			);
		}).catch(() => content.find(".starcompany-product-results").html(`<div class="text-danger">${__("Unable to load products.")}</div>`));
	}

	call("current_user").then((response) => {
		const user = response.message.data;
		canWrite = (user.roles || []).includes("System Manager");
		content.html(
			'<div class="form-layout"><div class="form-page">' +
			'<div class="form-dashboard-section"><div class="section-head">' + __("Product management") + "</div>" +
			'<div class="flex mb-3"><input class="form-control starcompany-product-search" placeholder="' + __("Search by name") + '">' +
			'<button class="btn btn-primary ml-2 product-search">' + __("Search") + "</button>" +
			(canWrite ? '<button class="btn btn-default ml-2 product-new">' + __("New product") + "</button>" : "") +
			'</div><div class="starcompany-product-results"></div></div></div></div>'
		);
		content.on("click", ".product-search", () => loadProducts(1));
		content.on("click", ".product-new", () => productDialog());
		content.on("click", ".product-view", (event) => showProduct($(event.currentTarget).data("id")));
		content.on("click", ".product-delete", (event) => deleteProduct($(event.currentTarget).data("id"), $(event.currentTarget).data("name")));
		content.on("click", ".product-previous", () => loadProducts(currentPage - 1));
		content.on("click", ".product-next", () => loadProducts(currentPage + 1));
		content.on("keydown", ".starcompany-product-search", (event) => { if (event.key === "Enter") loadProducts(1); });
		loadProducts(1);
	}).catch(() => content.html(`<div class="text-danger">${__("Unable to load Starcompany identity.")}</div>`));
};