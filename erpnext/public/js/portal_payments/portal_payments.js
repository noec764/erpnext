import Vue from 'vue/dist/vue.js';
import PaymentSelector from './PaymentSelector.vue';

Vue.prototype.__ = window.__;
Vue.prototype.frappe = window.frappe;

frappe.ready(() => {
	new Vue({
		el: '#mainview',
		render: h => h(PaymentSelector)
	})
})