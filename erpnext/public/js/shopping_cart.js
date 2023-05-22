// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// shopping cart
frappe.provide("erpnext.e_commerce.shopping_cart");
var shopping_cart = erpnext.e_commerce.shopping_cart;

var getParams = function (url) {
	var params = [];
	var parser = document.createElement('a');
	parser.href = url;
	var query = parser.search.substring(1);
	var vars = query.split('&');
	for (var i = 0; i < vars.length; i++) {
		var pair = vars[i].split('=');
		params[pair[0]] = decodeURIComponent(pair[1]);
	}
	return params;
};

frappe.ready(function () {
	var full_name = frappe.session && frappe.session.user_fullname;
	// update user
	if (full_name) {
		$('.navbar li[data-label="User"] a')
			.html('<i class="fa fa-fixed-width fa fa-user"></i> ' + full_name);
	}
	// set coupon code and sales partner code

	var url_args = getParams(window.location.href);

	var referral_coupon_code = url_args['cc'];
	var referral_sales_partner = url_args['sp'];

	var d = new Date();
	// expires within 30 minutes
	d.setTime(d.getTime() + (0.02 * 24 * 60 * 60 * 1000));
	var expires = "expires=" + d.toUTCString();
	if (referral_coupon_code) {
		document.cookie = "referral_coupon_code=" + referral_coupon_code + ";" + expires + ";path=/";
	}
	if (referral_sales_partner) {
		document.cookie = "referral_sales_partner=" + referral_sales_partner + ";" + expires + ";path=/";
	}
	referral_coupon_code = frappe.get_cookie("referral_coupon_code");
	referral_sales_partner = frappe.get_cookie("referral_sales_partner");

	if (referral_coupon_code && $(".tot_quotation_discount").val() == undefined) {
		$(".txtcoupon").val(referral_coupon_code);
	}
	if (referral_sales_partner) {
		$(".txtreferral_sales_partner").val(referral_sales_partner);
	}

	// update login
	shopping_cart.set_cart_count();
	shopping_cart.show_cart_navbar();
});

$.extend(shopping_cart, {
	update_cart: function (opts) {
		if (frappe.session.user === "Guest") {
			if (localStorage) {
				localStorage.setItem("last_visited", window.location.pathname);
			}
			frappe.call('erpnext.e_commerce.api.get_guest_redirect_on_action').then((res) => {
				window.location.href = res.message || "/login";
			});
		} else {
			shopping_cart.freeze();
			return frappe.call({
				type: "POST",
				method: "erpnext.e_commerce.shopping_cart.cart.update_cart",
				args: {
					item_code: opts.item_code,
					qty: opts.qty,
					booking: opts.booking,
					additional_notes: opts.additional_notes !== undefined ? opts.additional_notes : undefined,
					with_items: opts.with_items || 0,
					uom: opts.uom,
				},
				btn: opts.btn,
				callback: function(r) {
					shopping_cart.unfreeze();
					shopping_cart.set_cart_count(true);
					if(opts.callback)
						opts.callback(r);
				}
			});
		}
	},

	bind_place_order: function() {
		$(".cart-container").on("click", ".btn-place-order", async function() {
			const address = await frappe.call({
				method: 'erpnext.e_commerce.shopping_cart.cart.get_customer_address',
				freeze: true,
			})

			if (!address.message) {
				try {
					await shopping_cart.new_cart_address(false);
				} catch (e) {
					if (e) console.error(e);
				}
			}

			shopping_cart.place_order(this);
		});
	},

	bind_request_quotation: function() {
		$(".cart-container").on('click', '.btn-request-for-quotation', function() {
			shopping_cart.request_quotation(this);
		});
	},

	place_order: function(btn) {
		shopping_cart.freeze();

		return frappe.call({
			type: "POST",
			method: "erpnext.e_commerce.shopping_cart.cart.place_order",
			btn: btn,
			always(r) {
				if (r.exc) {
					shopping_cart.unfreeze();
					shopping_cart._show_error_after_action(r);
				} else {
					$(btn).hide();
					window.location.href = r.message;
				}
			},
		});
	},

	request_quotation: function(btn) {
		shopping_cart.freeze();

		return frappe.call({
			type: "POST",
			method: "erpnext.e_commerce.shopping_cart.cart.request_for_quotation",
			btn: btn,
			always(r) {
				if (r.exc) {
					shopping_cart.unfreeze();
					shopping_cart._show_error_after_action(r);
				} else {
					$(btn).hide();
					window.location.href = '/quotations/' + encodeURIComponent(r.message);
				}
			}
		});
	},

	set_cart_count: function(animate=false) {
		$(".intermediate-empty-cart").remove();

		var cart_count = frappe.get_cookie("cart_count");
		if (frappe.session.user === "Guest") {
			cart_count = 0;
		}

		if (cart_count) {
			$(".shopping-cart").toggleClass('hidden', false);
		}

		var $cart = $('.cart-icon');
		var $badge = $cart.find("#cart-count");

		if (parseInt(cart_count) === 0 || cart_count === undefined) {
			$cart.css("display", "none");
			$(".cart-tax-items").hide();
			$(".btn-place-order").hide();
			$(".cart-sticky-sidebar").hide();

			let intermediate_empty_cart_msg = `
				<div class="text-center w-100 intermediate-empty-cart mt-4 mb-4 text-muted">
					${ __("Cart is Empty") }
				</div>
			`;
			$(".cart-table").after(intermediate_empty_cart_msg);
		}
		else {
			$cart.css("display", "inline");
			$("#cart-count").text(cart_count);
		}

		if (cart_count) {
			$badge.html(cart_count);

			if (animate) {
				$cart.addClass("cart-animate");
				setTimeout(() => {
					$cart.removeClass("cart-animate");
				}, 500);
			}
		} else {
			$badge.remove();
		}
	},

	render_from_server_side(values) {
		const restoreFocusTo = this._dompath(document.activeElement);

		const elements = [
			[$(".cart-items"), values.items],
			[$(".cart-tax-items"), values.total],
			[$(".cart-summary"), values.summary],
			[$(".cart-addresses"), values.cart_address],
		];
		for (const [$element, value] of elements) {
			$element.html(value ?? "");
		}

		if (restoreFocusTo) {
			document.querySelector(restoreFocusTo)?.focus();
		}
	},

	/** @param {HTMLElement?} element */
	_dompath(element) {
		// inspired by https://stackoverflow.com/a/22072325
		let path = "";
		while (element) {
			const tag = element.tagName.toLowerCase();
			const classes = element.className.trim().split(/\s+/).join(".").replace(/^(.)/, ".$1");

			if (tag === "html" || tag === "body") break;

			path = path ? " > " + path : "";
			if (element.id) {
				return "#" + element.id + path;
			} else {
				let selector = tag + classes;
				// const idx = Array.from(element.parentElement?.children ?? [])?.indexOf(element) ?? -1;
				// if (idx >= 0) {
				// 	selector = selector + ":nth-child(" + (idx + 1) + ")";
				// }
				path = selector + path;
			}

			element = element.parentElement;
		}
		return path;
	},

	_fetch_and_rerender() {
		return frappe.call({
			method: "erpnext.e_commerce.shopping_cart.cart.rerender_cart",
			always(r) {
				if (!r.exc) {
					shopping_cart.render_from_server_side(r.message);
					// shopping_cart.set_cart_count();
				}
			}
		});
	},

	clear_error() {
		$("#cart-error").empty().toggle(false);
	},

	show_error(msg) {
		$("#cart-error").html(msg).toggle(true);
	},

	_show_error_after_action(response) {
		if (response.exc) {
			let msg = __("Something went wrong!");
			try {
				if (response._server_messages) {
					msg = JSON.parse(response._server_messages).map(m => JSON.parse(m))
					msg = msg.map(m => typeof m === 'object' ? m.message : m)
					msg = msg.join("<br>");
				}
			} catch (e) {
				console.error(e);
			}

			shopping_cart.show_error(msg);
			shopping_cart._fetch_and_rerender();
		} else {
			console.error(response);
		}
	},

	shopping_cart_update: function ({ item_code, qty, cart_dropdown, additional_notes, uom, booking }) {
		if (frappe.freeze_count) return;
		frappe.freeze();
		return shopping_cart.update_cart({
			item_code,
			qty,
			additional_notes,
			with_items: 1,
			btn: this,
			uom: uom,
			booking: booking,
			callback: function(r) {
				if(!r.exc) {
					frappe.unfreeze();
					shopping_cart.clear_error();
					shopping_cart.render_from_server_side(r.message);
					shopping_cart.set_cart_count();

					if (cart_dropdown != true) {
						$(".cart-icon").hide();
					}
				}
			},
		});
	},

	show_cart_navbar: function () {
		frappe.call({
			method: "erpnext.e_commerce.doctype.e_commerce_settings.e_commerce_settings.is_cart_enabled",
			callback: function(r) {
				$(".shopping-cart").toggleClass('hidden', r.message ? false : true);
			}
		});
	},

	new_cart_address: function (reload, addressType) {
		return new Promise((resolve, reject) => {
			const d = new frappe.ui.Dialog({
				title: __('New Address'),
				fields: [
					{
						label: __('Address Title'),
						fieldname: 'address_title',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('Address Line 1'),
						fieldname: 'address_line1',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('Address Line 2'),
						fieldname: 'address_line2',
						fieldtype: 'Data'
					},
					{
						label: __('City/Town'),
						fieldname: 'city',
						fieldtype: 'Data',
						reqd: 1
					},
					{
						label: __('State'),
						fieldname: 'state',
						fieldtype: 'Data'
					},
					{
						label: __('Country'),
						fieldname: 'country',
						fieldtype: 'Link',
						options: 'Country',
						reqd: 1,
						only_select: 1
					},
					{
						fieldname: "column_break0",
						fieldtype: "Column Break",
						width: "50%"
					},
					{
						label: __('Address Type'),
						fieldname: 'address_type',
						fieldtype: 'Select',
						options: [
							{ label: __('Billing'), value: 'Billing' },
							{ label: __('Shipping'), value: 'Shipping' }
						],
						default: addressType || 'Shipping',
						reqd: 1
					},
					{
						label: __('Postal Code'),
						fieldname: 'pincode',
						fieldtype: 'Data'
					},
					{
						fieldname: "phone",
						fieldtype: "Data",
						label: __("Phone")
					},
				],
				primary_action_label: __('Save'),
				primary_action: async (values) => {
					shopping_cart.freeze();

					try {
						const r = await frappe.call('erpnext.e_commerce.shopping_cart.cart.add_new_address', { doc: values })
						const r2 = await shopping_cart.update_cart_address(r.message.address_type, r.message.name)

						resolve();
						d.hide();

						reload && window.location.reload();
					} catch (error) {
						reject(error);
					} finally {
						shopping_cart.unfreeze();
					}
				}
			})
			d.$wrapper.find(".modal-content").addClass("frappe-card");
			d.on_hide = () => reject(); // reject the promise when closing the modal, if not resolved first
			d.show();
		});
	},

	update_cart_address(address_type, address_name) {
		return new Promise((resolve, reject) => {
			shopping_cart.freeze();

			frappe.call({
				method: "erpnext.e_commerce.shopping_cart.cart.update_cart_address",
				args: { address_type, address_name },
				always(r) {
					console.log(r);
					if (r.exc) {
						shopping_cart._show_error_after_action(r);
						reject(r);
					} else {
						shopping_cart.clear_error();
						shopping_cart.render_from_server_side(r.message);
						resolve(r);
					}
					shopping_cart.unfreeze();
				},
			});
		});
	},

	bind_add_to_cart_action() {
		$('.page_content').on('click', '.btn-add-to-cart-list', (e) => {
			const $btn = $(e.currentTarget);
			$btn.prop('disabled', true);

			if (frappe.session.user==="Guest") {
				if (localStorage) {
					localStorage.setItem("last_visited", window.location.pathname);
				}
				frappe.call('erpnext.e_commerce.api.get_guest_redirect_on_action').then((res) => {
					window.location.href = res.message || "/login";
				});
				return;
			}

			$btn.addClass('hidden');
			$btn.closest('.cart-action-container').addClass('d-flex');
			$btn.parent().find('.go-to-cart').removeClass('hidden');
			$btn.parent().find('.go-to-cart-grid').removeClass('hidden');
			$btn.parent().find('.cart-indicator').removeClass('hidden');

			const item_code = $btn.data('item-code');
			erpnext.e_commerce.shopping_cart.update_cart({
				item_code,
				qty: 1,
				cart_dropdown: true
			});

		});
	},

	freeze() {
		if (window.location.pathname !== "/cart" && window.location.pathname !== "/checkout") {
			return;
		}

		if (!$('#freeze').length) {
			let freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.appendTo("body");

			setTimeout(function() {
				freeze.addClass("in");
			}, 1);
		} else {
			$("#freeze").addClass("in");
		}
	},

	unfreeze() {
		if ($('#freeze').length) {
			let freeze = $('#freeze').removeClass("in");
			setTimeout(function() {
				freeze.remove();
			}, 1);
		}
	}
});
