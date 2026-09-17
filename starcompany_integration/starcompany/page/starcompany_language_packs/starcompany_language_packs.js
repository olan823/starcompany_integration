frappe.pages["starcompany-language-packs"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Starcompany"), single_column: true });
	const content = $('<div class="starcompany-language-packs"></div>').appendTo(page.main);
	let currentPage = 1;
	let canWrite = false;
	let products = [];

	const key = () => window.crypto && window.crypto.randomUUID
		? window.crypto.randomUUID()
		: `${Date.now()}-${Math.random().toString(36).slice(2)}`;
	const call = (method, args = {}) => frappe.call({ method: `starcompany_integration.api.proxy.${method}`, args });
	const upstream = (response) => response.message.data.data;
	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));

	function structureDialog(structure = null) {
		let operationKey = null;
		const dialog = new frappe.ui.Dialog({
			title: structure ? __("Edit language pack") : __("New language pack"),
			fields: [
				{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1, default: structure?.name || "" },
				{
					fieldtype: "MultiSelectList", fieldname: "product_ids", label: __("Products"), reqd: 1,
					get_data: (text) => products.filter((item) => item.description.toLowerCase().includes((text || "").toLowerCase())),
					default: (structure?.product_ids || []).map(String),
				},
				{
					fieldtype: "Select", fieldname: "chip_type", label: __("Chip type"), reqd: !structure,
					options: structure ? [structure.chip_type] : ["AD156", "TR2601S005-1"],
					default: structure?.chip_type || "AD156", read_only: Boolean(structure),
				},
			],
			primary_action_label: __("Save"),
			primary_action(values) {
				operationKey = operationKey || key();
				const button = dialog.get_primary_btn().prop("disabled", true);
				call("save_voice_pack_structure", {
					structure_id: structure?.id || null,
					name: values.name,
					product_ids: JSON.stringify((values.product_ids || []).map(Number)),
					chip_type: values.chip_type,
					idempotency_key: operationKey,
				}).then(() => {
					dialog.hide();
					frappe.show_alert({ message: __("Language pack saved."), indicator: "green" });
					loadStructures(currentPage);
				}).catch(() => frappe.msgprint(__("Unable to save the language pack. You can retry safely.")))
					.finally(() => button.prop("disabled", false));
			},
		});
		dialog.show();
	}

	function addLanguage(structureId, refresh) {
		call("voice_options", { structure_id: structureId }).then((response) => {
			const options = upstream(response).map((group) => ({ label: `${group.name} (${group.lang})`, value: group.lang }));
			let operationKey = null;
			const dialog = new frappe.ui.Dialog({
				title: __("Add language"),
				fields: [{ fieldtype: "Select", fieldname: "lang", label: __("Language"), reqd: 1, options: options.map((item) => item.value) }],
				primary_action_label: __("Add"),
				primary_action(values) {
					operationKey = operationKey || key();
					call("add_voice_pack_language", { structure_id: structureId, lang: values.lang, idempotency_key: operationKey })
						.then(() => { dialog.hide(); refresh(); })
						.catch(() => frappe.msgprint(__("Unable to add the language. You can retry safely.")));
				},
			});
			dialog.show();
		});
	}

	function addTimbre(structureId, language, refresh) {
		call("voice_options", { structure_id: structureId }).then((response) => {
			const group = upstream(response).find((item) => item.lang === language.lang);
			let operationKey = null;
			const dialog = new frappe.ui.Dialog({
				title: __("Add timbre"),
				fields: [{
					fieldtype: "MultiSelectList", fieldname: "timbres", label: __("Timbres"), reqd: 1,
					get_data: (text) => (group?.voices || []).filter((voice) => voice.name.toLowerCase().includes((text || "").toLowerCase())).map((voice) => ({ label: voice.name, value: voice.code })),
				}],
				primary_action_label: __("Add"),
				primary_action(values) {
					operationKey = operationKey || key();
					call("add_voice_pack_timbres", { language_id: language.id, timbres: JSON.stringify(values.timbres || []), idempotency_key: operationKey })
						.then(() => { dialog.hide(); refresh(); })
						.catch(() => frappe.msgprint(__("Unable to add the timbre. You can retry safely.")));
				},
			});
			dialog.show();
		});
	}

	function showItems(timbre) {
		call("voice_pack_items", { timbre_id: timbre.id }).then((response) => {
			const payload = upstream(response);
			const rows = payload.items.map((item) => `<tr><td>${escape(item.key)}</td><td>${escape(item.content)}</td>` +
				`<td>${item.generated ? __("Generated") : __("Pending")}</td><td class="text-right">${item.size}</td>` +
				`<td>${canWrite && !item.generated ? `<button class="btn btn-default btn-xs generate-item" data-id="${item.id}">${__("Generate")}</button>` : ""}</td></tr>`
			).join("") || `<tr><td colspan="5" class="text-muted text-center">${__("No voice items found.")}</td></tr>`;
			const dialog = new frappe.ui.Dialog({
				title: escape(timbre.name), size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "items", options: '<table class="table table-bordered"><thead><tr>' +
					`<th>${__("Key")}</th><th>${__("Content")}</th><th>${__("Status")}</th><th>${__("Size")}</th><th>${__("Actions")}</th>` +
					`</tr></thead><tbody>${rows}</tbody></table>` }],
			});
			dialog.$wrapper.on("click", ".generate-item", (event) => {
				const button = $(event.currentTarget).prop("disabled", true);
				call("generate_voice_pack_item", { item_id: button.data("id"), idempotency_key: key() })
					.then(() => { dialog.hide(); showItems(timbre); })
					.catch(() => frappe.msgprint(__("Unable to generate this voice item.")))
					.finally(() => button.prop("disabled", false));
			});
			dialog.show();
		});
	}

	function showStructure(structureId) {
		const dialog = new frappe.ui.Dialog({ title: __("Language pack details"), size: "extra-large", fields: [{ fieldtype: "HTML", fieldname: "body" }] });
		const refresh = () => call("voice_pack_languages", { structure_id: structureId }).then((response) => {
			const payload = upstream(response);
			const structure = payload.structure;
			const languageBlocks = payload.languages.map((language) => {
				const timbreRows = language.timbres.map((timbre) => `<tr><td>${escape(timbre.name)}</td><td>${escape(timbre.code)}</td>` +
					`<td>${timbre.not_generated_count} / ${timbre.item_count}</td><td>` +
					`<button class="btn btn-default btn-xs show-items" data-timbre="${timbre.id}">${__("Items")}</button>` +
					(canWrite ? ` <button class="btn btn-danger btn-xs delete-timbre" data-timbre="${timbre.id}">${__("Delete")}</button>` : "") +
					"</td></tr>").join("") || `<tr><td colspan="4" class="text-muted">${__("No timbres.")}</td></tr>`;
				return `<div class="mb-4"><div class="flex justify-between align-center"><h5>${escape(language.name)} (${escape(language.lang)})</h5><div>` +
					(canWrite ? `<button class="btn btn-default btn-xs add-timbre" data-language="${language.id}">${__("Add timbre")}</button> ` +
					`<button class="btn btn-danger btn-xs delete-language" data-language="${language.id}">${__("Delete language")}</button>` : "") +
					`</div></div><table class="table table-bordered"><thead><tr><th>${__("Timbre")}</th><th>${__("Code")}</th>` +
					`<th>${__("Pending / total")}</th><th>${__("Actions")}</th></tr></thead><tbody>${timbreRows}</tbody></table></div>`;
			}).join("") || `<div class="text-muted">${__("No languages.")}</div>`;
			dialog.fields_dict.body.$wrapper.html(
				`<div class="mb-3"><strong>${escape(structure.name)}</strong> · ${escape(structure.chip_type)} · ${__("Sync status")}: ${structure.sync_status}</div>` +
				(canWrite ? `<div class="mb-3"><button class="btn btn-default btn-sm add-language">${__("Add language")}</button> ` +
				`<button class="btn btn-default btn-sm generate-all">${__("Generate all")}</button> ` +
				`<button class="btn btn-default btn-sm generation-progress">${__("Generation progress")}</button> ` +
				`<button class="btn btn-primary btn-sm sync-pack">${__("Sync")}</button></div>` : "") + languageBlocks
			);
			dialog.$wrapper.off("click.starcompany");
			dialog.$wrapper.on("click.starcompany", ".add-language", () => addLanguage(structureId, refresh));
			dialog.$wrapper.on("click.starcompany", ".add-timbre", (event) => {
				const language = payload.languages.find((item) => item.id === Number($(event.currentTarget).data("language")));
				addTimbre(structureId, language, refresh);
			});
			dialog.$wrapper.on("click.starcompany", ".show-items", (event) => {
				const timbreId = Number($(event.currentTarget).data("timbre"));
				const timbre = payload.languages.flatMap((item) => item.timbres).find((item) => item.id === timbreId);
				showItems(timbre);
			});
			dialog.$wrapper.on("click.starcompany", ".delete-language", (event) => {
				const languageId = $(event.currentTarget).data("language");
				frappe.confirm(__("Delete this language and all its timbres?"), () => call("delete_voice_pack_language", { language_id: languageId, idempotency_key: key() }).then(refresh));
			});
			dialog.$wrapper.on("click.starcompany", ".delete-timbre", (event) => {
				const timbreId = $(event.currentTarget).data("timbre");
				frappe.confirm(__("Delete this timbre?"), () => call("delete_voice_pack_timbre", { timbre_id: timbreId, idempotency_key: key() }).then(refresh));
			});
			dialog.$wrapper.on("click.starcompany", ".generate-all", () => frappe.confirm(__("Generate all pending voice items?"), () => call("generate_voice_pack_structure", { structure_id: structureId, idempotency_key: key() }).then(refresh)));
			dialog.$wrapper.on("click.starcompany", ".generation-progress", () => call("voice_pack_generation", { structure_id: structureId }).then((result) => {
				const progress = upstream(result);
				frappe.msgprint(__("{0}: {1}% ({2}/{3})", [progress.message, progress.progress, progress.current, progress.total]));
			}));
			dialog.$wrapper.on("click.starcompany", ".sync-pack", () => frappe.confirm(__("Sync this complete language pack to the cloud platform?"), () => call("sync_voice_pack_structure", { structure_id: structureId, idempotency_key: key() }).then(refresh)));
		});
		refresh().then(() => dialog.show()).catch(() => frappe.msgprint(__("Unable to load language pack details.")));
	}

	function loadStructures(pageNumber) {
		const name = content.find(".voice-pack-search").val() || "";
		content.find(".voice-pack-results").html(`<div class="text-muted">${__("Loading...")}</div>`);
		call("voice_pack_structures", { page: pageNumber, page_size: 20, name }).then((response) => {
			const payload = upstream(response);
			currentPage = payload.pagination.page;
			const rows = payload.items.map((structure) => `<tr><td>${escape(structure.name)}</td>` +
				`<td>${escape(structure.products.map((item) => [item.vendor, item.model].filter(Boolean).join(" ")).join(", "))}</td>` +
				`<td>${escape(structure.chip_type)}</td><td>${structure.sync_status}</td><td>` +
				`<button class="btn btn-default btn-xs structure-view" data-id="${structure.id}">${__("Details")}</button>` +
				(canWrite ? ` <button class="btn btn-default btn-xs structure-edit" data-id="${structure.id}">${__("Edit")}</button> ` +
				`<button class="btn btn-danger btn-xs structure-delete" data-id="${structure.id}" data-name="${escape(structure.name)}">${__("Delete")}</button>` : "") +
				"</td></tr>").join("") || `<tr><td colspan="5" class="text-muted text-center">${__("No language packs found.")}</td></tr>`;
			content.find(".voice-pack-results").html('<table class="table table-bordered"><thead><tr>' +
				`<th>${__("Name")}</th><th>${__("Products")}</th><th>${__("Chip type")}</th><th>${__("Sync status")}</th><th>${__("Actions")}</th>` +
				`</tr></thead><tbody>${rows}</tbody></table><div class="flex justify-between align-center"><span class="text-muted">${__("{0} records", [payload.pagination.total])}</span>` +
				`<div><button class="btn btn-default btn-sm structure-previous" ${currentPage <= 1 ? "disabled" : ""}>${__("Previous")}</button> ` +
				`<button class="btn btn-default btn-sm structure-next" ${currentPage >= payload.pagination.last_page ? "disabled" : ""}>${__("Next")}</button></div></div>`);
			content.data("structures", payload.items);
		}).catch(() => content.find(".voice-pack-results").html(`<div class="text-danger">${__("Unable to load language packs.")}</div>`));
	}

	Promise.all([call("current_user"), call("products", { page: 1, page_size: 100 })]).then(([userResponse, productResponse]) => {
		canWrite = (userResponse.message.data.roles || []).includes("System Manager");
		products = upstream(productResponse).items.flatMap((product) => (product.models || []).map((model) => ({
			value: String(product.id), description: `${product.name} · ${product.vendor} ${model}`,
		})));
		content.html('<div class="form-layout"><div class="form-page"><div class="form-dashboard-section">' +
			`<div class="section-head">${__("Language pack management")}</div><div class="flex mb-3">` +
			`<input class="form-control voice-pack-search" placeholder="${__("Search by name")}"><button class="btn btn-primary ml-2 voice-pack-submit">${__("Search")}</button>` +
			(canWrite ? `<button class="btn btn-default ml-2 voice-pack-new">${__("New language pack")}</button>` : "") +
			'</div><div class="voice-pack-results"></div></div></div></div>');
		content.on("click", ".voice-pack-submit", () => loadStructures(1));
		content.on("click", ".voice-pack-new", () => structureDialog());
		content.on("click", ".structure-view", (event) => showStructure($(event.currentTarget).data("id")));
		content.on("click", ".structure-edit", (event) => {
			const structure = (content.data("structures") || []).find((item) => item.id === Number($(event.currentTarget).data("id")));
			structureDialog(structure);
		});
		content.on("click", ".structure-delete", (event) => frappe.confirm(__("Delete language pack {0}?", [$(event.currentTarget).data("name")]), () => call("delete_voice_pack_structure", { structure_id: $(event.currentTarget).data("id"), idempotency_key: key() }).then(() => loadStructures(currentPage))));
		content.on("click", ".structure-previous", () => loadStructures(currentPage - 1));
		content.on("click", ".structure-next", () => loadStructures(currentPage + 1));
		content.on("keydown", ".voice-pack-search", (event) => { if (event.key === "Enter") loadStructures(1); });
		loadStructures(1);
	}).catch(() => content.html(`<div class="text-danger">${__("Unable to initialize language pack management.")}</div>`));
};