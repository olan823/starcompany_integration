frappe.pages["starcompany-iot-card"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("IoT card"),
		single_column: true,
	});
	const content = $('<div class="starcompany-iot-card"></div>').appendTo(page.main);
	const escape = frappe.utils.escape_html;

	function valueOrDash(value) {
		return value === null || value === undefined || value === "" ? "-" : escape(String(value));
	}

	function flowText(value) {
		return value === null || value === undefined || value === "" ? "-" : `${escape(String(value))} KB`;
	}

	function onlineText(value) {
		if (Number(value) === 1) return __("Online");
		if (Number(value) === 2) return __("Offline");
		return __("Unknown");
	}

	function renderResult(result) {
		const status = result.status || {};
		const packages = Array.isArray(result.packages) ? result.packages : [];
		const rows = packages.map((item) => (
			"<tr>" +
				`<td>${valueOrDash(item.showname)}</td>` +
				`<td>${valueOrDash(item.package_type)}</td>` +
				`<td>${valueOrDash(item.flow)}</td>` +
				`<td>${valueOrDash(item.package_price)}</td>` +
				`<td>${valueOrDash(item.periods)}</td>` +
			"</tr>"
		)).join("") || `<tr><td colspan="5" class="text-muted text-center">${__("No available packages.")}</td></tr>`;

		content.find(".iot-card-result").html(
			'<div class="section-head">' + __("Query result") + "</div>" +
			'<table class="table table-bordered"><tbody>' +
				`<tr><th>${__("Card number")}</th><td>${valueOrDash(status.cardno)}</td><th>${__("ICCID")}</th><td>${valueOrDash(status.iccid)}</td></tr>` +
				`<tr><th>${__("Status")}</th><td>${valueOrDash(status.message || status.state)}</td><th>${__("Expiration date")}</th><td>${valueOrDash(status.expired_at)}</td></tr>` +
				`<tr><th>${__("Used data")}</th><td>${flowText(status.used)}</td><th>${__("Remaining data")}</th><td>${flowText(status.surplus)}</td></tr>` +
				`<tr><th>${__("Current package")}</th><td>${valueOrDash(status.autoname)}</td><th>${__("Online status")}</th><td>${onlineText(status.power_status)}</td></tr>` +
			"</tbody></table>" +
			'<div class="section-head">' + __("Available packages") + "</div>" +
			'<div class="table-responsive"><table class="table table-bordered"><thead><tr>' +
				`<th>${__("Package")}</th><th>${__("Type")}</th><th>${__("Data")}</th><th>${__("Price")}</th><th>${__("Validity")}</th>` +
			`</tr></thead><tbody>${rows}</tbody></table></div>`
		);
	}

	function queryCard() {
		const cardNumber = content.find(".iot-card-number").val().trim();
		if (!cardNumber) {
			frappe.msgprint(__("Enter an IoT card number."));
			return;
		}
		if (cardNumber.length > 100) {
			frappe.msgprint(__("IoT card number must not exceed 100 characters."));
			return;
		}

		const button = content.find(".iot-card-query").prop("disabled", true);
		content.find(".iot-card-result").html(`<div class="text-muted">${__("Loading...")}</div>`);
		frappe.call({
			method: "starcompany_integration.api.proxy.iot_card",
			args: { card_number: cardNumber },
		}).then((response) => renderResult(response.message.data.data))
			.catch(() => content.find(".iot-card-result").html(`<div class="text-danger">${__("Unable to query this IoT card.")}</div>`))
			.finally(() => button.prop("disabled", false));
	}

	content.html(
		'<div class="form-layout"><div class="form-page">' +
		'<div class="form-dashboard-section"><div class="section-head">' + __("IoT card query") + "</div>" +
		'<div class="text-muted mb-3">' + __("Query card status, data balance, and available packages.") + "</div>" +
		'<div class="flex mb-4"><input class="form-control iot-card-number" maxlength="100" placeholder="' + __("Enter IoT card number") + '">' +
		'<button class="btn btn-primary ml-2 iot-card-query">' + __("Query") + "</button></div>" +
		'<div class="iot-card-result"><div class="text-muted">' + __("Enter a card number to query.") + "</div></div>" +
		"</div></div></div>"
	);
	content.on("click", ".iot-card-query", queryCard);
	content.on("keydown", ".iot-card-number", (event) => {
		if (event.key === "Enter") queryCard();
	});
};