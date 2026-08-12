import sys
from frappe import _


def run():
	"""Verify _resolve_discount and _get_invoice_discount_fields handle all modes correctly."""
	from luxury_api.api.sales_invoice_pos import _resolve_discount, _get_invoice_discount_fields

	def test_resolve_no_discount():
		result = _resolve_discount({"discount_type": "No Discount"}, "Test")
		assert result == {}, f"Expected {{}}, got {result}"
		print("✓ Test 1: No Discount → {}")

	def test_resolve_percentage():
		result = _resolve_discount({"discount_type": "Percentage", "discount_percentage": 10}, "Test")
		assert result == {"discount_percentage": 10.0}, f"Expected discount_percentage 10, got {result}"
		print("✓ Test 2: Percentage with valid value (10) → {'discount_percentage': 10.0}")

	def test_resolve_amount():
		result = _resolve_discount({"discount_type": "Amount", "discount_amount": 50}, "Test")
		assert result == {"discount_amount": 50.0}, f"Expected discount_amount 50, got {result}"
		print("✓ Test 3: Amount with valid value (50) → {'discount_amount': 50.0}")

	def test_default_no_discount():
		result = _resolve_discount({}, "Test")
		assert result == {}, f"Expected default to No Discount (empty dict), got {result}"
		print("✓ Test 4: Missing discount_type defaults to No Discount → {}")

	def test_invalid_discount_type():
		import frappe
		try:
			_resolve_discount({"discount_type": "InvalidType"}, "Test")
			assert False, "Should have thrown for invalid discount_type"
		except frappe.ValidationError as e:
			assert "Invalid discount_type" in str(e), f"Expected 'Invalid discount_type' in error, got {e}"
			print("✓ Test 5: Invalid discount_type raises ValidationError")

	def test_percentage_missing_value():
		import frappe
		try:
			_resolve_discount({"discount_type": "Percentage"}, "Test")
			assert False, "Should have thrown for missing discount_percentage"
		except frappe.ValidationError:
			print("✓ Test 6: Percentage without value raises ValidationError")

	def test_percentage_out_of_range():
		import frappe
		try:
			_resolve_discount({"discount_type": "Percentage", "discount_percentage": 150}, "Test")
			assert False, "Should have thrown for percentage > 100"
		except frappe.ValidationError:
			print("✓ Test 7: Percentage > 100 raises ValidationError")

	def test_percentage_zero():
		import frappe
		try:
			_resolve_discount({"discount_type": "Percentage", "discount_percentage": 0}, "Test")
			assert False, "Should have thrown for percentage = 0"
		except frappe.ValidationError:
			print("✓ Test 8: Percentage = 0 raises ValidationError")

	def test_amount_missing_value():
		import frappe
		try:
			_resolve_discount({"discount_type": "Amount"}, "Test")
			assert False, "Should have thrown for missing discount_amount"
		except frappe.ValidationError:
			print("✓ Test 9: Amount without value raises ValidationError")

	def test_amount_zero():
		import frappe
		try:
			_resolve_discount({"discount_type": "Amount", "discount_amount": 0}, "Test")
			assert False, "Should have thrown for amount = 0"
		except frappe.ValidationError:
			print("✓ Test 10: Amount = 0 raises ValidationError")

	def test_amount_negative():
		import frappe
		try:
			_resolve_discount({"discount_type": "Amount", "discount_amount": -50}, "Test")
			assert False, "Should have thrown for amount < 0"
		except frappe.ValidationError:
			print("✓ Test 11: Amount < 0 raises ValidationError")

	def test_invoice_discount_no_discount():
		result = _get_invoice_discount_fields({"discount_type": "No Discount"})
		assert result == {}, f"Expected {{}}, got {result}"
		print("✓ Test 12: Invoice-level No Discount → {}")

	def test_invoice_discount_percentage():
		result = _get_invoice_discount_fields({"discount_type": "Percentage", "discount_percentage": 15})
		assert result == {"apply_discount_on": "Grand Total", "discount_percentage": 15.0}, f"Expected apply_discount_on + discount_percentage, got {result}"
		print("✓ Test 13: Invoice-level Percentage adds apply_discount_on")

	def test_invoice_discount_amount():
		result = _get_invoice_discount_fields({"discount_type": "Amount", "discount_amount": 100})
		assert result == {"apply_discount_on": "Grand Total", "discount_amount": 100.0}, f"Expected apply_discount_on + discount_amount, got {result}"
		print("✓ Test 14: Invoice-level Amount adds apply_discount_on")

	def test_independent_item_and_invoice():
		item_result = _resolve_discount({"discount_type": "Percentage", "discount_percentage": 5}, "Item 1")
		invoice_result = _get_invoice_discount_fields({"discount_type": "Amount", "discount_amount": 20})
		assert item_result == {"discount_percentage": 5.0}, f"Item should have discount_percentage, got {item_result}"
		assert invoice_result == {"apply_discount_on": "Grand Total", "discount_amount": 20.0}, f"Invoice should have apply_discount_on + discount_amount, got {invoice_result}"
		print("✓ Test 15: Item and invoice discount resolve independently")

	tests = [
		test_resolve_no_discount,
		test_resolve_percentage,
		test_resolve_amount,
		test_default_no_discount,
		test_invalid_discount_type,
		test_percentage_missing_value,
		test_percentage_out_of_range,
		test_percentage_zero,
		test_amount_missing_value,
		test_amount_zero,
		test_amount_negative,
		test_invoice_discount_no_discount,
		test_invoice_discount_percentage,
		test_invoice_discount_amount,
		test_independent_item_and_invoice,
	]

	for test_fn in tests:
		try:
			test_fn()
		except AssertionError as e:
			print(f"✗ {test_fn.__name__}: {e}")
			sys.exit(1)

	print("\n✅ All discount field checks passed.")


if __name__ == "__main__":
	run()
