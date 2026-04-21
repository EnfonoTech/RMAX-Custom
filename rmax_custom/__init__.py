__version__ = "0.0.1"


def _apply_monkey_patches():
	try:
		from rmax_custom.overrides.landed_cost_gl import apply_patch

		apply_patch()
	except Exception:
		import frappe

		frappe.log_error(frappe.get_traceback(), "rmax_custom: landed_cost_gl patch failed")


_apply_monkey_patches()
