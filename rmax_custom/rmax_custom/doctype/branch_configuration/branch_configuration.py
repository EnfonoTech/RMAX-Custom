# User permissions are created for company, branch, warehouse and cost center.
# Company and first warehouse are set as is_default=1 so Frappe uses them as
# the user's Session Defaults instead of falling back to global defaults.

import frappe
from frappe.model.document import Document


class BranchConfiguration(Document):

	def validate(self):
		# Ensure warehouse and cost center belong to the selected company
		if self.company:
			for w in self.warehouse:
				if w.warehouse:
					wh_company = frappe.db.get_value("Warehouse", w.warehouse, "company")
					if wh_company and wh_company != self.company:
						frappe.throw(
							f"Warehouse <b>{w.warehouse}</b> belongs to company <b>{wh_company}</b>, "
							f"not <b>{self.company}</b>. Please select a warehouse from the correct company."
						)

			for c in self.cost_center:
				if c.cost_center:
					cc_company = frappe.db.get_value("Cost Center", c.cost_center, "company")
					if cc_company and cc_company != self.company:
						frappe.throw(
							f"Cost Center <b>{c.cost_center}</b> belongs to company <b>{cc_company}</b>, "
							f"not <b>{self.company}</b>. Please select a cost center from the correct company."
						)

	def before_save(self):
		if self.is_new():
			return

		old_doc = self.get_doc_before_save()

		old_users = {d.user for d in old_doc.user}
		new_users = {d.user for d in self.user}

		removed_users = old_users - new_users

		for user in removed_users:
			# Delete company permission
			if old_doc.get("company"):
				delete_permission(user, "Company", old_doc.company)

			delete_permission(user, "Branch", old_doc.branch)

			for w in old_doc.warehouse:
				delete_permission(user, "Warehouse", w.warehouse)

			for c in old_doc.cost_center:
				delete_permission(user, "Cost Center", c.cost_center)

		# Handle company change — remove old company permission for remaining users
		old_company = old_doc.get("company")
		new_company = self.get("company")
		if old_company and old_company != new_company:
			for u in self.user:
				delete_permission(u.user, "Company", old_company)

	def on_update(self):
		self.create_permissions()

	def create_permissions(self):
		# Determine the first warehouse to mark as default
		default_warehouse = self.warehouse[0].warehouse if self.warehouse else None

		for u in self.user:
			# Create company permission (marked as default so Session Defaults picks it)
			if self.company:
				create_permission(u.user, "Company", self.company, is_default=1)

			create_permission(u.user, "Branch", self.branch)

			for idx, w in enumerate(self.warehouse):
				# First warehouse is the default
				create_permission(u.user, "Warehouse", w.warehouse, is_default=1 if idx == 0 else 0)

			for c in self.cost_center:
				create_permission(u.user, "Cost Center", c.cost_center)


def create_permission(user, allow, value, is_default=0):
	if not value:
		return

	existing = frappe.db.exists("User Permission", {
		"user": user,
		"allow": allow,
		"for_value": value
	})

	if existing:
		# Update is_default if needed (e.g. re-saving Branch Configuration)
		if is_default:
			frappe.db.set_value("User Permission", existing, "is_default", 1)
	else:
		doc = frappe.new_doc("User Permission")
		doc.user = user
		doc.allow = allow
		doc.for_value = value
		doc.is_default = is_default
		doc.apply_to_all_doctypes = 1
		doc.insert(ignore_permissions=True)


def delete_permission(user, allow, value):
	if not value:
		return

	perms = frappe.get_all(
		"User Permission",
		filters={
			"user": user,
			"allow": allow,
			"for_value": value
		},
		pluck="name"
	)

	for p in perms:
		frappe.delete_doc("User Permission", p, ignore_permissions=True)
