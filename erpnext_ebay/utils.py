from __future__ import unicode_literals
import frappe
import json

from .ebay_requests import get_request
from vlog import ebaydebug,vwrite
from bs4 import BeautifulSoup
import types

def disable_ebay_sync_for_item(item, rollback=False):
    """Disable Item if not exist on ebay"""
    if rollback:
        frappe.db.rollback()

    item.sync_with_ebay = 0
    item.sync_qty_with_ebay = 0
    item.save(ignore_permissions=True)
    frappe.db.commit()

def disable_ebay_sync_on_exception():
	frappe.db.rollback()
	frappe.db.set_value("Ebay Settings", None, "enable_ebay", 0)
	frappe.db.commit()


def make_ebay_log(title="Sync Log", status="Queued", method="sync_ebay", message=None, exception=False,
                     name=None, request_data={}):
    # ebaydebug("DEBUG START ==>")
    # ebaydebug("title: %s, status: %s, method: %s, message: %s, exception: %s, name: %s, request_data: %s" %(title, status, method, message, exception,name, request_data))
    make_log_flag = True
    # log_message = message if message else frappe.get_traceback()
    # log_query = """select name from `tabEbay Log` where title = '%s' and message='%s' and method='%s' and status='%s' and request_data='%s'""" %(title[0:140],log_message,method,status,json.dumps(request_data))
    log_query = """select name from `tabEbay Log` where title = '%s' and method='%s' and request_data='%s'""" % (
    title[0:140].replace("'","''"), method, json.dumps(request_data))
    # ebaydebug(log_query)
    if status!="Queued" and title!="Sync Completed":
        if len(frappe.db.sql(log_query, as_dict=1)) > 0:
            make_log_flag = False
    if make_log_flag:
        if not name:
            name = frappe.db.get_value("Ebay Log", {"status": "Queued"})

            if name:
                """ if name not provided by log calling method then fetch existing queued state log"""
                log = frappe.get_doc("Ebay Log", name)

            else:
                """ if queued job is not found create a new one."""
                log = frappe.get_doc({"doctype": "Ebay Log"}).insert(ignore_permissions=True)

            if exception:
                frappe.db.rollback()
                log = frappe.get_doc({"doctype": "Ebay Log"}).insert(ignore_permissions=True)

            log.message = message if message else frappe.get_traceback()
            log.title = title[0:140]
            log.method = method
            log.status = status
            log.request_data = json.dumps(request_data)

            log.save(ignore_permissions=True)
            frappe.db.commit()
    # ebaydebug("DEBUG END <==")

def get_message_body_from_code(message_body_code,message_body_params={}):
    vwrite("in get_message_body_from_code")
    # vwrite(type(message_body_params))
    # vwrite(message_body_params)
    # if not message_body_params:
    #     message_body_params = json.loads(message_body_params)
    message_body = ""
    if (message_body_code == "sales_order_for_led_tv"):
        message_body = """
            Dear Sir/Mam,

            Thank You for your Purchase of LED TV from Ebay from us!
            
            We look forward to providing excellent service to you!
            
            Following are the value added services that we also Provide:
            
            1. To get wall Mount with the TV itself please purchase it here(https://www.usedyetnew.com/search?q=wall+mount) as per the size of the TV.
            2. Extended Warranty Support: 
               We are Delighted to introduce Extended Warranty for our Esteemed Customers at 25% discount if bought before shipping. Check the links Below to Purchase the Same.
            3. You will receive a separate Invoice with Warranty with Original Product invoice mentioned in Same!
                1 Year Extended Warranty (https://www.usedyetnew.com/search?q=1+Year+extended+warranty)
                2 Years Extended Warranty (https://www.usedyetnew.com/search?q=2+Year+extended+warranty)
            
            Following Are the key Points that I will like to bring to your Notice:

            1. 1 Year PAN India WARRANTY! Shop With Confidence! We are a established company started by IIT/IIM/X-Googlers dealing in Consumer Goods We provide no hassle 1 year Pan India Warranty with defect rate below 0.001%. In case you face any issue, simply reach out to our customer care email or phone number. We will pick up, fix and get the unit back for you within 7 days!
            2. The Product includes: TV Set, Remote, TV legs, Used manual, power cord. (Same as any New TV Bought). This does not include wall mounting brackets. Again regular Brands also do not provide it as part of unit box. This is a brand new Sealed Unit
            3. 100% Genuine Samsung Panel: This is 100% Genuine Samsung Panel product. Please note in order to keep imported goods tax obligations low, we import Front Samsung Panel and high quality back Body separately. The same is simply put together in our controlled environment. This process is replication of the standard process followed by most established Brands also to keep tax obligation low. For this reason we will not be able to put Samsung Logo on same unless requested by the customer
            
            Best Regards,
            Team 
            Usedyetnew.com
        """
    elif (message_body_code == "delivery_note_for_led_tv"):
        message_body = """
            Dear Sir/Mam,

            Your LED TV has been shipped and we hope you love your New Purchase.

            We have taken extreme care to send it in Top Condition and hope you take care of below to protect yourself from any Shipping Mishap.

            To Avail Ebay Guarantee in case of mishap please make sure you have captured your TV Unboxing and testing on Video:

            1. Before the courier person leaves, please inspect the package for any damage or wetness. Take the photo of the same and in writing with your signature mention 'the package looks damaged' and hand over the document to the courier person. Please take the photo of the written document too. Kindly accept the package
            2. When you Open your Ebay package, please make sure you are making video of unboxing.
            3. Clearly take the video of label on package showing your and our address
            4. Unpack the TV from the top. First remove the top thermocol and then the side thermocols.
            5. Hold the LED from the side and then take it out of the carton.
            6. DO NOT PUT ANY PRESSURE ON THE TV PANEL.
            7. Plug the TV and confirm if the screen displays the Logo.
            8. Important: All above steps should be clearly captured on video to protect your Ebay Claim.

            Thank you for your Purchase. Your unit will reach you shortly!

            Best Regards,
            Team 
            Usedyetnew.com
            """
    elif(message_body_code == "delivery_note_for_other_items"):
        customer_name = message_body_params.get("customer_name")
        item_name = message_body_params.get("item_name")
        video_link = message_body_params.get("video_link")
        message_body = """
            Dear %s

            We have shipped your item %s. and we hope it reaches you soon!
            
            Please find the video here ( %s ) showing final Quality check and packing of your item.
            
            IMPORTANT: ITEM NEEDS TO BE OPENED UNDER VIDEO RECORDING TO CLAIM  ANY DAMAGE OR FUNCTIONAL ISSUES. 
            
            We take extreme care to ship a great product in great condition.
            Moment you receive your item. Kindly follow following steps:
                1. Receive product from courier.
                2. Record unboxing of product with your mobile camera
                3. Clearly show the name and address (from and to) printed on the box
                4. Clearly show opening of the box
                5. Check your item from all angles 
                6. Swtich on the item and conduct basic testing
            Note: Any claims for damage or major functional issues that are not recorded live during unboxing will not be entertained. 
            
            Questions? Write back to this email!
            
            Best Regards,
            Team 
            Usedyetnew.com
            """ % (customer_name,item_name,video_link)
    return message_body

def replace_with_newlines(element):
    text = ''
    for elem in element.recursiveChildGenerator():
        if isinstance(elem, types.StringTypes):
            text += elem.strip()
        elif elem.name == 'br':
            text += '\n'
    return text

@frappe.whitelist()
def send_ebay_m2m_message(itemid,subject,message_body_code,recipient,message_body_params=None,message_body=None,question_type="CustomizedSubject",attachments='[]',ignore_filter_conditions=False):
    # itemid - ebay_product_id
    # recipient - ebay_buyer_id
    # message_body_code - code to generate message body
    from .sync_products import upload_image_to_ebay
    if isinstance(attachments, basestring):
        attachments = json.loads(attachments)
    uploaded_images = []
    for a in attachments:
        if isinstance(a, basestring):
            attach = frappe.db.get_value("File", {"name": a},
                                         ["file_name", "file_url", "is_private"], as_dict=1)
            uploaded_image_url = upload_image_to_ebay('http://www.usedyetnew.com'+attach.get("file_url"))
            uploaded_images.append({'uploaded_image_url':uploaded_image_url,'uploaded_image_name':attach.get("file_name")})
    if not message_body:
        message_body = get_message_body_from_code(message_body_code,message_body_params)
    message_body = BeautifulSoup(message_body)
    formatted_message_body = ""
    lines = message_body.find("body")
    try:
        for line in lines.findAll(['div','p']):
            line = replace_with_newlines(line)
            formatted_message_body+= '\n '+line
    except Exception as e:
        vwrite(e.message)
    params = {"ItemID":itemid,"MemberMessage":{"Subject":subject,"Body":formatted_message_body,"QuestionType":question_type,"RecipientID":recipient}}
    if len(uploaded_images):
        params['MemberMessage']['MessageMedia'] = []
        for image in uploaded_images:
            params['MemberMessage']['MessageMedia'].append({'MediaName':image.get("uploaded_image_name"),'MediaURL':image.get("uploaded_image_url")})
    message = get_request('AddMemberMessageAAQToPartner', 'trading', params)
    if message.get("status_code")==200:
        return True
    else:
        return False
