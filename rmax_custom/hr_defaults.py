# Copyright (c) 2025, Rmax Custom and contributors
# For license information, please see license.txt

"""Default HR masters for RMAX — Employee Grades, Salary Components, and
Salary Structures.

Design decisions:

* Runs from ``after_migrate``. Idempotent — everything is created only when
  missing. Subsequent app updates NEVER overwrite manual edits made by the
  client.
* To reset a structure back to the shipped defaults after manual edits,
  rename or delete the existing row first (or use
  :func:`reset_sponsorship_salary_structures` explicitly via bench execute).
* Requires the ``hrms`` app. If HRMS is not installed, this module is a
  no-op so non-HR sites are unaffected.
"""

import frappe
from frappe import _


EMPLOYEE_GRADES = ["Sponsorship", "Non-Sponsorship"]

# (salary_component_name, abbr, type)
SALARY_COMPONENTS = [
	("Basic", "B", "Earning"),
	("Housing Allowance", "HA", "Earning"),
	("Transportation Allowance", "TA", "Earning"),
	("Food Allowance", "FA", "Earning"),
	("Other Allowance", "OA", "Earning"),
	("GOSI Employee", "GOSIE", "Deduction"),
]

# Percent of base gross, sums to 1.0
SPONSORSHIP_EARNINGS = [
	("Basic", 0.60),
	("Housing Allowance", 0.25),
	("Transportation Allowance", 0.10),
	("Food Allowance", 0.05),
]

SPONSORSHIP_STRUCTURE_PREFIX = "RMAX Sponsorship KSA"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def setup_hr_defaults():
	"""Create RMAX HR defaults if missing. Idempotent, no-op without HRMS."""
	if not _hrms_installed():
		return

	_ensure_employee_grades()
	_ensure_salary_components()
	_ensure_sponsorship_structures()


# ---------------------------------------------------------------------------
# Employee Grade
# ---------------------------------------------------------------------------


def _ensure_employee_grades():
	for grade in EMPLOYEE_GRADES:
		if frappe.db.exists("Employee Grade", grade):
			continue
		frappe.get_doc({
			"doctype": "Employee Grade",
			"__newname": grade,
			"name": grade,
		}).insert(ignore_permissions=True)

	frappe.db.commit()


# ---------------------------------------------------------------------------
# Salary Components
# ---------------------------------------------------------------------------


def _ensure_salary_components():
	for comp_name, abbr, comp_type in SALARY_COMPONENTS:
		if frappe.db.exists("Salary Component", comp_name):
			continue

		frappe.get_doc({
			"doctype": "Salary Component",
			"salary_component": comp_name,
			"salary_component_abbr": abbr,
			"type": comp_type,
			"depends_on_payment_days": 1 if comp_type == "Earning" else 0,
			"is_tax_applicable": 0,
			"variable_based_on_taxable_salary": 0,
		}).insert(ignore_permissions=True)

	frappe.db.commit()


# ---------------------------------------------------------------------------
# Sponsorship Salary Structure (per Company)
# ---------------------------------------------------------------------------


def _ensure_sponsorship_structures():
	if not frappe.db.exists("Employee Grade", "Sponsorship"):
		return

	companies = frappe.get_all("Company", fields=["name", "abbr"])
	for company in companies:
		structure_name = f"{SPONSORSHIP_STRUCTURE_PREFIX} - {company.abbr}"
		if frappe.db.exists("Salary Structure", structure_name):
			# Already present — never overwrite manual edits
			continue

		earnings = [
			{
				"salary_component": comp_name,
				"abbr": _component_abbr(comp_name),
				"amount_based_on_formula": 1,
				"formula": f"base * {ratio}",
				"depends_on_payment_days": 1,
			}
			for comp_name, ratio in SPONSORSHIP_EARNINGS
		]

		doc = frappe.get_doc({
			"doctype": "Salary Structure",
			"name": structure_name,
			"__newname": structure_name,
			"company": company.name,
			"is_active": "Yes",
			"payroll_frequency": "Monthly",
			"salary_slip_based_on_timesheet": 0,
			"currency": frappe.db.get_value("Company", company.name, "default_currency"),
			"earnings": earnings,
			"deductions": [],
		})
		doc.insert(ignore_permissions=True)
		# Keep as Draft — client reviews + submits when ready

	frappe.db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hrms_installed():
	try:
		installed = frappe.get_installed_apps()
	except Exception:
		return False
	return "hrms" in installed


def _component_abbr(component_name):
	return frappe.db.get_value("Salary Component", component_name, "salary_component_abbr") or ""


# ---------------------------------------------------------------------------
# Manual reset (call via bench execute when needed)
# ---------------------------------------------------------------------------


def reset_sponsorship_salary_structures(force=False):
	"""DESTRUCTIVE: deletes and recreates the shipped Sponsorship structures.

	Only intended for admin use during implementation. Skips any structure
	that is already submitted or assigned to an employee.

	Run::

	    bench --site <site> execute \
	        rmax_custom.hr_defaults.reset_sponsorship_salary_structures \
	        --kwargs '{"force": 1}'
	"""
	if not force:
		frappe.throw(_("Pass force=1 to confirm deletion of shipped salary structures."))

	companies = frappe.get_all("Company", fields=["abbr"])
	for company in companies:
		structure_name = f"{SPONSORSHIP_STRUCTURE_PREFIX} - {company.abbr}"
		if not frappe.db.exists("Salary Structure", structure_name):
			continue

		ss = frappe.get_doc("Salary Structure", structure_name)
		if ss.docstatus == 1:
			frappe.msgprint(
				_("Skipping submitted Salary Structure {0}").format(structure_name)
			)
			continue

		assigned = frappe.db.exists(
			"Salary Structure Assignment",
			{"salary_structure": structure_name, "docstatus": ["!=", 2]},
		)
		if assigned:
			frappe.msgprint(
				_("Skipping {0} — assigned to an employee").format(structure_name)
			)
			continue

		frappe.delete_doc("Salary Structure", structure_name, ignore_permissions=True)

	frappe.db.commit()
	setup_hr_defaults()
