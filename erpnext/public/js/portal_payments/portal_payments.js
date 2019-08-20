import Vue from 'vue/dist/vue.js';
import PaymentSelector from './PaymentSelector.vue';

if (!window.Vue) {
	Vue.prototype.__ = window.__;
	Vue.prototype.frappe = window.frappe;
	window.Vue = Vue;
}

new Vue({
	el: '#mainview',
	render: h => h(PaymentSelector)
})