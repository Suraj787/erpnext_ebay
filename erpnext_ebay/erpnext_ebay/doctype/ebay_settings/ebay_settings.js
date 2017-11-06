// Copyright (c) 2017, vwithv1602 and contributors
// For license information, please see license.txt

frappe.provide("erpnext_ebay.ebay_settings");

frappe.ui.form.on("Ebay Settings", "onload", function(frm, dt, dn){
	frappe.call({
		method:"erpnext_ebay.erpnext_ebay.doctype.ebay_settings.ebay_settings.get_series",
		callback:function(r){
		    console.log(r)
			$.each(r.message, function(key, value){
				set_field_options(key, value)
			})
		}
	})
//	erpnext_ebay.ebay_settings.setup_queries(frm);
})

frappe.ui.form.on('Ebay Settings', {
	refresh: function(frm) {
        if(!frm.doc.__islocal && frm.doc.enable_ebay === 1){
            frm.add_custom_button(__('Sync Ebay'), function() {
                frappe.call({
                    method:"erpnext_ebay.api.sync_ebay",
                })
            }).addClass("btn-primary");
        }
        frm.add_custom_button(__("Ebay Log"), function(){
            frappe.set_route("List", "Ebay Log");
        })
        /* >> Developer Options*/
        frm.add_custom_button(__("Fetch Active Listings"), function() {
            frappe.call({
               method:"erpnext_ebay.developer_actions.get_active_listing",
               args: {},
               callback: function(r) {
                   alert("Im in callback")
               }
            });
        }, __("Developer Actions"));
        frm.add_custom_button(__("Enable is_purchase_item"), function() {
            frappe.call({
               method:"erpnext_ebay.developer_actions.enable_is_purchase_item",
               args: {},
               callback: function(r) {
                   alert("Enabled is_purchase_item")
               }
            });
        }, __("Developer Actions"));
        /* << Developer Options*/
	}
});
