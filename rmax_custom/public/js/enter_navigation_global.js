/**
 * RMAX Custom: Global Enter Key Navigation
 *
 * Replaces Tab behavior with Enter key across ALL doctypes:
 * - Main form: Enter moves to the next visible, editable field
 * - Child tables: Enter moves across columns, then to next row, then adds new row
 * - Does NOT trigger submit (prevents accidental submission)
 */

(function () {
	"use strict";

	$(document).on("keydown", function (e) {
		if (e.key !== "Enter") return;

		var $active = $(document.activeElement);
		if (!$active.length) return;

		// Don't intercept Enter on buttons, dialogs, or awesomebar
		if (
			$active.is("button") ||
			$active.closest(".modal-dialog").length ||
			$active.closest(".awesomplete").length ||
			$active.closest("#navbar-search").length ||
			$active.is("textarea") // Allow Enter for newlines in textareas
		) {
			return;
		}

		// Don't intercept if Ctrl/Cmd+Enter (used for submit)
		if (e.ctrlKey || e.metaKey) return;

		// ─── CHILD TABLE (Grid) ───
		if ($active.closest(".grid-row").length) {
			e.preventDefault();
			e.stopImmediatePropagation();
			_handle_grid_enter($active);
			return;
		}

		// ─── MAIN FORM FIELDS ───
		if ($active.closest(".frappe-control").length && cur_frm) {
			e.preventDefault();
			e.stopImmediatePropagation();
			_handle_form_enter($active);
			return;
		}
	});

	function _handle_grid_enter($active) {
		var $row = $active.closest(".grid-row");
		var grid = _get_grid_from_element($active);
		if (!grid) return;

		// Get all editable inputs in current row
		var $inputs = $row
			.find("input, select, textarea")
			.filter(":visible:not([readonly]):not([disabled])");

		var idx = $inputs.index(document.activeElement);

		// Move to next column in same row
		if (idx >= 0 && idx < $inputs.length - 1) {
			$inputs.eq(idx + 1).focus();
			if ($inputs.eq(idx + 1).is("input")) {
				$inputs.eq(idx + 1).select();
			}
			return;
		}

		// Last column → next row
		var row_idx = grid.grid_rows.indexOf(grid.get_row($row.attr("data-name")));
		if (row_idx >= 0 && row_idx < grid.grid_rows.length - 1) {
			var next_row = grid.grid_rows[row_idx + 1];
			next_row.activate();
			setTimeout(function () {
				var $nextInputs = $(next_row.row)
					.find("input, select, textarea")
					.filter(":visible:not([readonly]):not([disabled])");
				if ($nextInputs.length) {
					$nextInputs.eq(0).focus();
					if ($nextInputs.eq(0).is("input")) $nextInputs.eq(0).select();
				}
			}, 100);
			return;
		}

		// Last row, last column → add new row
		grid.add_new_row();
		setTimeout(function () {
			var rows = grid.grid_rows;
			var new_row = rows[rows.length - 1];
			if (!new_row) return;
			new_row.activate();
			var $newInputs = $(new_row.row)
				.find("input, select, textarea")
				.filter(":visible:not([readonly]):not([disabled])");
			if ($newInputs.length) {
				$newInputs.eq(0).focus();
				if ($newInputs.eq(0).is("input")) $newInputs.eq(0).select();
			}
		}, 150);
	}

	function _handle_form_enter($active) {
		if (!cur_frm) return;

		// Get all visible, editable fields on the form
		var $form = cur_frm.$wrapper || $(cur_frm.wrapper);
		var $all_inputs = $form
			.find(
				".frappe-control:visible:not(.hide-control) input:visible:not([readonly]):not([disabled])," +
				".frappe-control:visible:not(.hide-control) select:visible:not([readonly]):not([disabled])"
			)
			.not(".grid-row input, .grid-row select") // Exclude child table inputs (handled separately)
			.not("[data-fieldtype='Table'] input");

		var idx = $all_inputs.index(document.activeElement);

		if (idx >= 0 && idx < $all_inputs.length - 1) {
			$all_inputs.eq(idx + 1).focus();
			if ($all_inputs.eq(idx + 1).is("input")) {
				$all_inputs.eq(idx + 1).select();
			}
		}
		// On last field, do nothing (don't submit)
	}

	function _get_grid_from_element($el) {
		var $grid_wrapper = $el.closest(".frappe-control[data-fieldtype='Table']");
		if (!$grid_wrapper.length || !cur_frm) return null;

		var fieldname = $grid_wrapper.attr("data-fieldname");
		if (fieldname && cur_frm.fields_dict[fieldname] && cur_frm.fields_dict[fieldname].grid) {
			return cur_frm.fields_dict[fieldname].grid;
		}
		return null;
	}
})();
