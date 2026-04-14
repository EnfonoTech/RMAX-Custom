# User permissions are created for company, branch, warehouse and cost center.
# Company and first warehouse are set as is_default=1 so Frappe uses them as
# the user's Session Defaults instead of falling back to global defaults.
# The "Branch User" role is auto-assigned to users added here.

import frappe
from frappe.model.document import Document

BRANCH_USER_ROLE = "Branch User"


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

			# Remove Branch User role if user is not in any other Branch Configuration
			_maybe_remove_branch_user_role(user, exclude_branch=self.name)

		# Handle company change — remove old company permission for remaining users
		old_company = old_doc.get("company")
		new_company = self.get("company")
		if old_company and old_company != new_company:
			for u in self.user:
				delete_permission(u.user, "Company", old_company)

	def on_update(self):
		self.create_permissions()

	def create_permissions(self):
		for u in self.user:
			# Create company permission (marked as default so Session Defaults picks it)
			if self.company:
				create_permission(u.user, "Company", self.company, is_default=1)

			create_permission(u.user, "Branch", self.branch)

			for idx, w in enumerate(self.warehouse):
				# First warehouse is the default
				create_permission(u.user, "Warehouse", w.warehouse, is_default=1 if idx == 0 else 0)

			for idx, c in enumerate(self.cost_center):
				# First cost center is the default
				create_permission(u.user, "Cost Center", c.cost_center, is_default=1 if idx == 0 else 0)

			# Also grant access to the company's default cost center (used in tax templates)
			# without marking it as default — the branch cost center stays as the user's default
			if self.company:
				company_default_cc = frappe.db.get_value("Company", self.company, "cost_center")
				if company_default_cc:
					create_permission(u.user, "Cost Center", company_default_cc, is_default=0)

			# Auto-assign Branch User role
			_assign_branch_user_role(u.user)


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


def _assign_branch_user_role(user):
	"""Assign Branch User role if not already assigned."""
	if not frappe.db.exists("Role", BRANCH_USER_ROLE):
		return

	user_doc = frappe.get_doc("User", user)
	existing_roles = [r.role for r in user_doc.roles]
	if BRANCH_USER_ROLE not in existing_roles:
		user_doc.add_roles(BRANCH_USER_ROLE)


def _maybe_remove_branch_user_role(user, exclude_branch=None):
	"""Remove Branch User role if user is not in any other Branch Configuration."""
	filters = {"user": user}
	other_configs = frappe.get_all(
		"Branch Configuration User",
		filters=filters,
		fields=["parent"],
	)

	# Check if user exists in any Branch Configuration OTHER than the excluded one
	in_other_branch = any(
		c.parent != exclude_branch for c in other_configs
	)

	if not in_other_branch:
		user_doc = frappe.get_doc("User", user)
		if BRANCH_USER_ROLE in [r.role for r in user_doc.roles]:
			user_doc.remove_roles(BRANCH_USER_ROLE)
