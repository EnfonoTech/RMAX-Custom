#user permissions are created for branch, warehouse and cost center.

import frappe
from frappe.model.document import Document


class BranchConfiguration(Document):

	def before_save(self):

		if self.is_new():
			return

		old_doc = self.get_doc_before_save()

		old_users = {d.user for d in old_doc.user}
		new_users = {d.user for d in self.user}

		removed_users = old_users - new_users

		for user in removed_users:

			delete_permission(user, "Branch", old_doc.branch)

			for w in old_doc.warehouse:
				delete_permission(user, "Warehouse", w.warehouse)

			for c in old_doc.cost_center:
				delete_permission(user, "Cost Center", c.cost_center)

	def on_update(self):
		self.create_permissions()

	def create_permissions(self):

		for u in self.user:

			create_permission(u.user, "Branch", self.branch)

			for w in self.warehouse:
				create_permission(u.user, "Warehouse", w.warehouse)

			for c in self.cost_center:
				create_permission(u.user, "Cost Center", c.cost_center)

def create_permission(user, allow, value):

	if not value:
		return

	if not frappe.db.exists("User Permission", {
		"user": user,
		"allow": allow,
		"for_value": value
	}):

		doc = frappe.new_doc("User Permission")
		doc.user = user
		doc.allow = allow
		doc.for_value = value
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