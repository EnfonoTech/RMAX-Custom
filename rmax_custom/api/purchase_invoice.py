import frappe

@frappe.whitelist()
def create_single_purchase_invoice(receipt_names):
    import json
    if isinstance(receipt_names, str):
        receipt_names = json.loads(receipt_names)

    # Get first receipt for header info
    pr = frappe.get_doc("Purchase Receipt", receipt_names[0])

    # Create new Purchase Invoice
    pi = frappe.new_doc("Purchase Invoice")
    pi.supplier = pr.supplier
    pi.company = pr.company
    pi.currency = pr.currency
    pi.buying_price_list = pr.buying_price_list
    pi.remarks = "Created from: " + ", ".join(receipt_names)

    # Get all items from all receipts
    for receipt_name in receipt_names:
        receipt = frappe.get_doc("Purchase Receipt", receipt_name)
        for item in receipt.items:
            pi.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "description": item.description,
                "qty": item.qty,
                "rate": item.rate,
                "uom": item.uom,
                "warehouse": item.warehouse,
                "purchase_receipt": receipt_name,
                "purchase_receipt_item": item.name,
                "expense_account": item.expense_account,
                "cost_center": item.cost_center
            })

    pi.insert(ignore_permissions=True)
    frappe.db.commit()
    return pi.name
