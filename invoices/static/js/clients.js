(function () {
	"use strict";

	let clientType = document.getElementById("client_type_radio");
	let vatNumberFields = document.getElementById("vat_number_fields");

	// This removes the hidden value when the radio button is already set.
	// This can occure when a validation error happend.
	let clientTypeValue = clientType.querySelector(
		'input[name="client_type"]:checked'
	)?.value;

	if (clientTypeValue && clientTypeValue === "Company") {
		vatNumberFields.classList.remove("hidden");
	}

	clientType.addEventListener("change", (e) => {
		if (e.target.value === "Company") {
			vatNumberFields.classList.remove("hidden");
		} else {
			vatNumberFields.classList.add("hidden");
		}
	});
})();
