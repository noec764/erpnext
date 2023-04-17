// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// JS exclusive to /cart page
frappe.provide("erpnext.e_commerce.shopping_cart");
var shopping_cart = erpnext.e_commerce.shopping_cart;

$.extend(shopping_cart, {
	bind_events: function() {
		shopping_cart.bind_change_qty();
		shopping_cart.bind_remove_cart_item();
		shopping_cart.bind_change_notes();
		shopping_cart.bind_coupon_code();
		shopping_cart.bind_place_order();
		shopping_cart.bind_request_quotation();
	},

	bind_change_qty: function() {
		// bind update button
		$(".cart-items").on("change", ".cart-qty", function() {
			var item_code = $(this).attr("data-item-code");
			var newVal = $(this).val();
			shopping_cart.shopping_cart_update({item_code, qty: newVal});
		});

		$(".cart-items").on('click', '.number-spinner button', function () {
			var btn = $(this),
				input = btn.closest('.number-spinner').find('input'),
				oldValue = input.val().trim(),
				newVal = 0;

			if (btn.attr('data-dir') == 'up') {
				newVal = parseInt(oldValue) + 1;
			} else {
				if (oldValue > 1) {
					newVal = parseInt(oldValue) - 1;
				}
			}
			input.val(newVal);

			let notes = input.closest("td").siblings().find(".notes").text().trim();
			var item_code = input.attr("data-item-code");
			shopping_cart.shopping_cart_update({
				item_code,
				qty: newVal,
				additional_notes: notes
			});
		});
	},

	bind_change_notes: function() {
		$('.cart-items').on('change', 'textarea', function() {
			const $textarea = $(this);
			const item_code = $textarea.attr('data-item-code');
			const qty = $textarea.closest('tr').find('.cart-qty').val() || 1;
			const notes = $textarea.val();
			shopping_cart.shopping_cart_update({
				item_code,
				qty,
				additional_notes: notes
			});
		});
	},

	bind_remove_cart_item: function() {
		$(".cart-items").on("click", ".remove-cart-item", (e) => {
			const $remove_cart_item_btn = $(e.currentTarget);
			const item_code = $remove_cart_item_btn.data("item-code");
			const item_booking = $remove_cart_item_btn.data("item-booking");

			shopping_cart.shopping_cart_update({
				item_code: item_code,
				qty: 0,
				booking: item_booking
			});
		});
	},

	bind_coupon_code: function() {
		$(".cart-container").on("click", ".bt-coupon", function() {
			shopping_cart.apply_coupon_code(this);
		});
	},

	apply_coupon_code: function(btn) {
		return frappe.call({
			type: "POST",
			method: "erpnext.e_commerce.shopping_cart.cart.apply_coupon_code",
			btn: btn,
			args : {
				applied_code : $('.txtcoupon').val(),
				applied_referral_sales_partner: $('.txtreferral_sales_partner').val()
			},
			callback: function(r) {
				if (r && r.message){
					location.reload();
				}
			}
		});
	}
});

frappe.ready(function() {
	if (window.location.pathname === "/cart") {
		$(".cart-icon").hide();
	}
	shopping_cart.parent = $(".cart-container");
	shopping_cart.bind_events();
});

function show_terms() {
	var html = $(".cart-terms").html();
	frappe.msgprint(html);
}
