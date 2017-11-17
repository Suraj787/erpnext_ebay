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
        function show_loader(){
            msgprint("Please wait while action is being performed.", 'Information')
        }
        function access(fn){
            var d = new frappe.ui.Dialog({
                title: __("Protected"),
                fields: [{
                    "label": "Authorization Code",
                    "fieldname":"auth_code",
                    "fieldtype":"Data",
                    "description":""
                }]
            });
            d.set_primary_action(__("Authorize"), function() {
                args = d.get_values();
                console.log(args)
                if(args.auth_code=='vamc@uyn'){
                    d.hide();
                    show_loader();
                    call_fn(fn)

                }
                else{
                    alert("Invalid code")
                    return false;
                }
            });
            d.show()
	    }
	    function call_fn(fn){
	        switch(fn){
                case 'enable_is_purchase_item':
                    access_enable_is_purchase_item();
                break;
                case 'get_active_listing':
                    access_get_active_listing();
                break;
                case 'check_m2m':
                    access_check_m2m();
                break;
                default:
                    alert("No option found.");
            }
	    }
	    function access_enable_is_purchase_item(){
	        frappe.call({
               method:"erpnext_ebay.developer_actions.enable_is_purchase_item",
               args: {},
               callback: function(r) {
                   msgprint("Enabled is_purchase_item","Information");
               }
            });
	    }
	    function access_get_active_listing(){
	        frappe.call({
               method:"erpnext_ebay.developer_actions.get_active_listing",
               args: {},
               callback: function(r) {
                   msgprint("Active listing items exported to devlogfile.txt","Information");
               }
            });
	    }
	    function access_check_m2m(){
            frappe.call({
               method:"erpnext_ebay.developer_actions.check_m2m",
               args: {},
               callback: function(r) {
                   msgprint("eBay M2M result exported to devlogfile.txt", "Information");
               }
              });
	    }
	    /* >> Buttons */
        /*frm.add_custom_button(__("Fetch Active Listings"), function() {
            access('get_active_listing')
        }, __("Developer Actions"));
        frm.add_custom_button(__("Enable is_purchase_item"), function() {
            access('enable_is_purchase_item')
        }, __("Developer Actions"));
        frm.add_custom_button(__("Check eBay M2M"), function() {
            access('check_m2m')
        }, __("Developer Actions"));*/
        /* << Buttons */
        /* << Developer Options*/
	}
});
