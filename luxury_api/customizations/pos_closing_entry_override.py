import frappe


class POSClosingEntryOverride:
	"""
	Mixin to override POS Closing Entry validation.
	Skips user ownership validation to allow multi-cashier closings from API.
	"""

	def validate_pos_invoices(self):
		"""
		Skip user ownership validation for POS Closing Entry.
		Allows invoices from multiple cashiers to be consolidated in one closing.
		"""
		invalid_rows = []

		for d in self.pos_invoices:
			invalid_row = {"idx": d.idx}
			pos_invoice = frappe.db.get_values(
				"POS Invoice",
				d.pos_invoice,
				["consolidated_invoice", "pos_profile", "docstatus"],
				as_dict=1,
			)[0]

			if pos_invoice.consolidated_invoice:
				invalid_row.setdefault("msg", []).append(frappe._("POS Invoice is already consolidated"))
				invalid_rows.append(invalid_row)
				continue

			if pos_invoice.pos_profile != self.pos_profile:
				invalid_row.setdefault("msg", []).append(
					frappe._("POS Profile doesn't match {}").format(frappe.bold(self.pos_profile))
				)
			if pos_invoice.docstatus != 1:
				invalid_row.setdefault("msg", []).append(frappe._("POS Invoice is not submitted"))

			# ponytail: skip user ownership check — API handles multi-cashier closings
			# if pos_invoice.owner != self.user:
			#     invalid_row.setdefault("msg", []).append(...)

			if invalid_row.get("msg"):
				invalid_rows.append(invalid_row)

		# Validate sales invoices
		if self.invoice_type == "Sales Invoice" or len(self.sales_invoices) > 0:
			for d in self.sales_invoices:
				invalid_row = {"idx": d.idx}
				sales_invoice = frappe.db.get_values(
					"Sales Invoice",
					d.sales_invoice,
					["pos_profile", "docstatus", "is_pos", "is_created_using_pos", "pos_closing_entry"],
					as_dict=1,
				)[0]

				if sales_invoice.pos_closing_entry:
					invalid_row.setdefault("msg", []).append(
						frappe._("Sales Invoice is already consolidated")
					)
					invalid_rows.append(invalid_row)
					continue

				if not sales_invoice.is_pos:
					invalid_row.setdefault("msg", []).append(frappe._("Sales Invoice does not have Payments"))
				if not sales_invoice.is_created_using_pos:
					invalid_row.setdefault("msg", []).append(frappe._("Sales Invoice is not created using POS"))
				if sales_invoice.pos_profile != self.pos_profile:
					invalid_row.setdefault("msg", []).append(
						frappe._("POS Profile doesn't match {}").format(frappe.bold(self.pos_profile))
					)
				if sales_invoice.docstatus != 1:
					invalid_row.setdefault("msg", []).append(frappe._("Sales Invoice is not submitted"))

				# ponytail: skip user ownership check
				# if sales_invoice.owner != self.user:
				#     invalid_row.setdefault("msg", []).append(...)

				if invalid_row.get("msg"):
					invalid_rows.append(invalid_row)

		if invalid_rows:
			error_list = []
			for row in invalid_rows:
				for msg in row.get("msg"):
					error_list.append(frappe._("Row #{}: {}").format(row.get("idx"), msg))
			frappe.throw(error_list, title=frappe._("Invalid POS Invoices"), as_list=True)
