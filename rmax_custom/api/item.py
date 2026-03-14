import frappe








@frappe.whitelist()
def create_party_specific_items(item, suppliers):
    """
    Create Party Specific Item records for multiple suppliers.
    creates a new record linking the supplier with
    the given item.
    """
    suppliers = frappe.parse_json(suppliers)
    for s in suppliers:
        supplier = s.get("supplier")
        if not frappe.db.exists("Party Specific Item", {
            "party_type": "Supplier",
            "party": supplier,
            "based_on": "Item Code",
            "based_on_value": item
        }):
            doc = frappe.new_doc("Party Specific Item")
            doc.party_type = "Supplier"
            doc.party = supplier
            doc.based_on = "Item Code"
            doc.based_on_value = item
            doc.item = item
            doc.insert(ignore_permissions=True)

    return "Done"