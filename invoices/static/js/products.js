(function () {
	"use strict";
	if (APIKEY === "[apikey]" || API_URL === "[api_url]") {
		throw Error(
			"APIKEY or API_URL was not set propperly. This page will not function."
		);
	}
	async function findProduct(product) {
		return fetch(`${API_URL}/find_product/${product}?apikey=${APIKEY}`, {
			mode: "cors",
			method: "GET",
		}).then((response) => {
			if (response.ok) {
				return response.json();
			}
			throw new Error("Something went wrong");
		});
	}

	async function productFromSku(product) {
		return fetch(`${API_URL}/product/${product}?apikey=${APIKEY}`, {
			mode: "cors",
			method: "GET",
		}).then((response) => {
			if (response.ok) {
				return response.json();
			}
			throw new Error("Something went wrong");
		});
	}

	function calcVat(productPrice, quantity, vat) {
		return ((productPrice * quantity) / 100) * vat;
	}

	const productsTable = {
		rowCount: 0,
		products: {},
		elements: {
			table: document.getElementById("products-table"),
			subtotalExc: document.getElementById("total-ex-display"),
			subtotalInc: document.getElementById("total-inc-display"),
			totalVat: document.getElementById("total-vat"),
		},
		subtotalExc: 0,
		subtotalInc: 0,
		totalVat: 0,
		addNewProduct: function (product) {
			this.updateTable(product);
		},
		resetCalculations: function () {
			this.subtotalExc = 0;
			this.subtotalInc = 0;
			this.totalVat = 0;
			this.totalVatInc = 0;
		},
		updateTable: function (product) {
			const VAT = calcVat(
				product.inputs.price,
				product.inputs.quantity,
				product.inputs.vat
			);
			const SUBTOTALEXC = product.inputs.price * product.inputs.quantity;
			const SUBTOTALINC = SUBTOTALEXC + VAT;

			this.subtotalExc += SUBTOTALEXC;
			this.subtotalInc += SUBTOTALINC;
			this.totalVat += VAT;

			this.createNewRow(product, SUBTOTALEXC, SUBTOTALINC, VAT);
			this.updateTableFooter();
		},
		createNewRow: function (product, SUBTOTALEXC, SUBTOTALINC, VAT) {
			const row = document.createElement("tr");
			row.innerHTML = `
                <input type="hidden" name="products-${this.rowCount}-name" value="${product.selected.name}" readonly>
                <input type="hidden" name="products-${this.rowCount}-product_sku" value="${product.selected.sku}" readonly>
                <input type="hidden" name="products-${this.rowCount}-price" value="${product.inputs.price}" readonly>
                <input type="hidden" name="products-${this.rowCount}-vat_percentage" value="${product.inputs.vat}" readonly>
                <input type="hidden" name="products-${this.rowCount}-quantity" value="${product.inputs.quantity}" readonly>
                `;
			row.setAttribute("id", `product-entry-${this.rowCount}`);
			const name = document.createElement("td");
			const sku = document.createElement("td");
			const price = document.createElement("td");
			const vatEl = document.createElement("td");
			const quantity = document.createElement("td");
			const subtotalExc = document.createElement("td");
			const totalVatEl = document.createElement("td");
			const subtotalInc = document.createElement("td");
			const actions = document.createElement("td");
			const deleteBtn = document.createElement("button");
			deleteBtn.classList.add("error");
			deleteBtn.innerHTML = "Delete";
			deleteBtn.setAttribute("type", "button");
			deleteBtn.addEventListener(
				"click",
				this.deleteRow.bind(this, row, this.rowCount)
			);

			// const editBtn = document.createElement("button");
			// editBtn.classList.add("info");
			// editBtn.innerHTML = "Edit";
			// editBtn.setAttribute("type", "button");
			// editBtn.addEventListener("click",
			//     this.editRow.bind(this, row, this.rowCount)
			// )

			name.innerHTML = product.selected.name;
			sku.innerHTML = product.selected.sku;
			price.innerHTML = `€&nbsp; ${product.inputs.price}`;
			vatEl.innerHTML = `${product.inputs.vat}%`;
			quantity.innerHTML = product.inputs.quantity;

			subtotalExc.innerHTML = `€&nbsp; ${SUBTOTALEXC.toFixed(2)}`;
			totalVatEl.innerHTML = `€&nbsp; ${VAT.toFixed(2)}`;
			subtotalInc.innerHTML = `€&nbsp; ${SUBTOTALINC.toFixed(2)}`;

			actions.appendChild(deleteBtn);
			// actions.appendChild(editBtn);
			row.appendChild(name);
			row.appendChild(sku);
			row.appendChild(price);
			row.appendChild(vatEl);
			row.appendChild(quantity);
			row.appendChild(subtotalExc);
			row.appendChild(totalVatEl);
			row.appendChild(subtotalInc);
			row.appendChild(actions);

			this.products[this.rowCount] = product;
			this.rowCount++;
			this.elements.table.tBodies[0].appendChild(row);
		},
		updateTableFooter: function () {
			this.elements.subtotalExc.innerHTML = `€&nbsp; ${this.subtotalExc.toFixed(
				2
			)}`;
			this.elements.totalVat.innerHTML = `€&nbsp; ${this.totalVat.toFixed(
				2
			)}`;
			this.elements.subtotalInc.innerHTML = `€&nbsp; ${this.subtotalInc.toFixed(
				2
			)}`;
		},
		deleteRow: function (row, rowIndex) {
			row.remove();
			delete this.products[rowIndex];

			this.resetCalculations();
			for (const [key, product] of Object.entries(this.products)) {
				const VAT = calcVat(
					product.inputs.price,
					product.inputs.quantity,
					product.inputs.vat
				);
				const SUBTOTALEXC =
					product.inputs.price * product.inputs.quantity;
				const SUBTOTALINC = SUBTOTALEXC + VAT;

				this.subtotalExc += SUBTOTALEXC;
				this.subtotalInc += SUBTOTALINC;
				this.totalVat += VAT;
			}
			this.updateTableFooter();
		},
		// editRow: function(row, rowIndex) {
		//     console.log(this.products[rowIndex]);
		// }
	};

	const popupform = {
		results: [],
		selected: null,
		table: null,
		elements: {
            overlay: document.getElementById("overlay"),
			form: document.getElementById("myForm"),
			resultsDiv: document.getElementById("results"),
			findProductInput: document.querySelector(
				"input[name='find_product']"
			),
			selectedProduct: document.querySelector(
				"input[name='selected-product']"
			),
			selectedProductSku: document.querySelector(
				"input[name='selected-product-sku']"
			),
			selectedProductPrice: document.querySelector(
				"input[name='selected-product-price']"
			),
			selectedProductVat: document.querySelector(
				"input[name='selected-product-vat']"
			),
			selectedProductQuantity: document.querySelector(
				"input[name='selected-product-quantity']"
			),
			saveButton: document.getElementById("save-form"),
		},
		init: function (table) {
			this.table = table;
			document
				.getElementById("close-form")
				.addEventListener("click", this.close.bind(this));
			document
				.getElementById("open-form")
				.addEventListener("click", this.open.bind(this));

			this.elements.findProductInput.addEventListener(
				"keyup",
				this.find.bind(this)
			);
			this.elements.selectedProductQuantity.addEventListener(
				"change",
				this.determinePrice.bind(this)
			);
			this.elements.saveButton.addEventListener(
				"click",
				this.save.bind(this)
			);
		},
		find: function () {
			if (this.elements.findProductInput.value.length <= 2) {
				return;
			}
			findProduct(this.elements.findProductInput.value).then((data) => {
                if (data.products) {
					this.results = data.products;
				} else {
					this.results = [];
				}
                this.displayResults();
			});
		},
		displayResults: function () {
			this.elements.resultsDiv.innerHTML = "";
			this.results.map((product) => {
				this.elements.resultsDiv.appendChild(
					this.createResultNode(product)
				);
			});
		},
		createResultNode: function (product) {
			const li = document.createElement("li");
			const container = document.createElement("div");
			container.classList.add("product-result");
			container.innerHTML = `
                <span><strong>Product: </strong>${product.name}</span>
                <span><strong>SKU: </strong>${product.sku}</span>
                <span><strong>Stock: </strong>${product.currentstock}</span>
            `;
			li.appendChild(container);
			li.addEventListener(
				"click",
				this.handleResultClick.bind(this, product)
			);
			return li;
		},
		handleResultClick: function (product) {
			this.selected = product;
			this.update();
		},
		update: function () {
			this.elements.selectedProduct.value = this.selected.name;
			this.elements.selectedProductSku.value = this.selected.sku;
			this.elements.selectedProductPrice.value =
				this.selected?.prices[0].price;

            //VAT_AMOUNT is loaded in from create.html
			this.elements.selectedProductVat.value = VAT_AMOUNT;
			if (!this.elements.selectedProductQuantity.value) {
				this.elements.selectedProductQuantity.value = 1;
			}
		},
		determinePrice: function () {
			if (!this.selected || !this.selected?.prices) {
				return;
			}

			for (let index = 0; index < this.selected.prices.length; index++) {
				const current_element = this.selected.prices[index];
				const next_element = this.selected.prices[index + 1];
				const quantity = this.elements.selectedProductQuantity.value;

				if (quantity == current_element.start_range) {
					this.elements.selectedProductPrice.value =
						current_element.price;
					return;
				}

				if (
					quantity > current_element.start_range &&
					next_element &&
					quantity < next_element.start_range
				) {
					this.elements.selectedProductPrice.value =
						current_element.price;
					return;
				}

				if (next_element === undefined) {
					this.elements.selectedProductPrice.value =
						current_element.price;
					return;
				}
			}
		},
		save: function () {
			this.table.addNewProduct({
				selected: this.selected,
				inputs: {
					quantity: this.elements.selectedProductQuantity.value,
					vat: this.elements.selectedProductVat.value,
					price: this.elements.selectedProductPrice.value,
				},
			});
			this.close();
		},
		open: function () {
			this.reset();
            this.elements.overlay.style.display = "block";
			this.elements.form.style.display = "flex";
            this.elements.findProductInput.focus()
            document.body.style.overflow = 'hidden';
		},
		close: function () {
			this.reset();
            this.elements.overlay.style.display = "none";
			this.elements.form.style.display = "none";
            document.body.style.overflow = '';
		},
		reset: function () {
			this.selected = null;
			this.results = [];
			this.elements.findProductInput.value = "";
			this.elements.resultsDiv.innerHTML = "";
			this.elements.selectedProduct.value = "";
			this.elements.selectedProductSku.value = "";
			this.elements.selectedProductPrice.value = "";
			this.elements.selectedProductVat.value = "";
			this.elements.selectedProductQuantity.value = "";
		},
	};

	popupform.init(productsTable);

	const form = JSON.parse(FORM_DATA);

	form.forEach((product, index) => {
		if (product.name === null) {
			return;
		}
		productFromSku(product.product_sku).then((data) => {
			productsTable.addNewProduct({
				selected: data,
				inputs: {
					quantity: product.quantity,
					vat: product.vat_percentage,
					price: product.price,
				},
			});
		});
	});
})();
