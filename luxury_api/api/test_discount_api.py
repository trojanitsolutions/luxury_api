"""Test create_sales_invoice with discount_type at both item and invoice levels."""

import frappe
from frappe.utils import flt


def run():
	"""Run all discount API tests."""

	def get_test_customer_company_pos():
		"""Use existing test data from bench."""
		company = "ABC PVT LTD"
		customer = "CUST-2026-00001"
		pos_profile = "POS Profile 1"
		warehouse = "Goods In Transit - APL"
		item = "STO-ITEM-2026-00003"
		return customer, company, pos_profile, warehouse, item

	def test_no_discount():
		"""Test: no discount_type at any level (backward compat)."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [{"item_code": item, "qty": 1}],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
		}

		result = create_sales_invoice(**payload)
		assert result["success"], f"Expected success, got {result}"

		doc = frappe.get_doc("Sales Invoice", result["data"]["name"])
		assert doc.discount_amount == 0, f"Invoice discount_amount should be 0, got {doc.discount_amount}"
		assert all(row.discount_percentage == 0 for row in doc.items), "Items should have no discount"
		print(f"✓ Test 1 (No Discount): grand_total={doc.grand_total}")

		# Cleanup
		doc.cancel()
		doc.delete()

	def test_invoice_percentage():
		"""Test: invoice-level percentage discount only."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [{"item_code": item, "qty": 10}],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
			"discount_type": "Percentage",
			"discount_percentage": 10,
		}

		result = create_sales_invoice(**payload)
		assert result["success"], f"Expected success, got {result}"

		doc = frappe.get_doc("Sales Invoice", result["data"]["name"])
		print(f"✓ Test 2 (Invoice Percentage): net_total={doc.net_total}, discount_amount={doc.discount_amount}, grand_total={doc.grand_total}")
		assert doc.additional_discount_percentage == 10, f"additional_discount_percentage should be 10, got {doc.additional_discount_percentage}"
		assert flt(doc.discount_amount, 2) > 0, f"discount_amount should be > 0, got {doc.discount_amount}"

		# Cleanup
		doc.cancel()
		doc.delete()

	def test_invoice_amount():
		"""Test: invoice-level amount discount only."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [{"item_code": item, "qty": 10}],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
			"discount_type": "Amount",
			"discount_amount": 50,
		}

		result = create_sales_invoice(**payload)
		assert result["success"], f"Expected success, got {result}"

		doc = frappe.get_doc("Sales Invoice", result["data"]["name"])
		print(f"✓ Test 3 (Invoice Amount): net_total={doc.net_total}, discount_amount={doc.discount_amount}, grand_total={doc.grand_total}")
		assert flt(doc.discount_amount, 2) == 50, f"discount_amount should be 50, got {doc.discount_amount}"

		# Cleanup
		doc.cancel()
		doc.delete()

	def test_item_percentage():
		"""Test: item-level percentage discount only."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [
				{"item_code": item, "qty": 2, "discount_type": "Percentage", "discount_percentage": 10},
			],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
		}

		result = create_sales_invoice(**payload)
		assert result["success"], f"Expected success, got {result}"

		doc = frappe.get_doc("Sales Invoice", result["data"]["name"])
		print(f"✓ Test 4 (Item Percentage): item.rate={doc.items[0].rate}, grand_total={doc.grand_total}")
		assert doc.items[0].discount_percentage == 10, f"Item discount_percentage should be 10, got {doc.items[0].discount_percentage}"

		# Cleanup
		doc.cancel()
		doc.delete()

	def test_item_amount():
		"""Test: item-level amount discount only."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [
				{"item_code": item, "qty": 2, "discount_type": "Amount", "discount_amount": 5},
			],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
		}

		result = create_sales_invoice(**payload)
		assert result["success"], f"Expected success, got {result}"

		doc = frappe.get_doc("Sales Invoice", result["data"]["name"])
		print(f"✓ Test 5 (Item Amount): item.discount_amount={doc.items[0].discount_amount}, grand_total={doc.grand_total}")
		assert flt(doc.items[0].discount_amount, 2) == 5, f"Item discount_amount should be 5, got {doc.items[0].discount_amount}"

		# Cleanup
		doc.cancel()
		doc.delete()

	def test_combined_item_and_invoice():
		"""Test: both item and invoice discounts combine (item applied first, then invoice)."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [
				{"item_code": item, "qty": 2, "discount_type": "Amount", "discount_amount": 5},
			],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
			"discount_type": "Percentage",
			"discount_percentage": 10,
		}

		result = create_sales_invoice(**payload)
		assert result["success"], f"Expected success, got {result}"

		doc = frappe.get_doc("Sales Invoice", result["data"]["name"])
		print(f"✓ Test 6 (Combined): item.discount_amount={doc.items[0].discount_amount}, invoice.discount_amount={doc.discount_amount}, grand_total={doc.grand_total}")

		# Cleanup
		doc.cancel()
		doc.delete()

	def test_invalid_discount_type():
		"""Test: invalid discount_type at invoice level."""
		customer, company, pos_profile, warehouse, item = get_test_customer_company_pos()

		from luxury_api.api.sales_invoice_pos import create_sales_invoice

		payload = {
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"warehouse": warehouse,
			"items": [{"item_code": item, "qty": 1}],
			"payments": [{"mode_of_payment": "Cash", "amount": 100}],
			"discount_type": "InvalidType",
		}

		result = create_sales_invoice(**payload)
		assert not result["success"], f"Expected failure, got {result}"
		assert "Invalid discount_type" in result["message"], f"Expected error about invalid discount_type, got {result['message']}"
		print(f"✓ Test 7 (Invalid invoice discount_type): error caught correctly")

	tests = [
		test_no_discount,
		test_invoice_percentage,
		test_invoice_amount,
		test_item_percentage,
		test_item_amount,
		test_combined_item_and_invoice,
		test_invalid_discount_type,
	]

	for test_fn in tests:
		try:
			test_fn()
		except AssertionError as e:
			print(f"✗ {test_fn.__name__}: {e}")
			import traceback
			traceback.print_exc()
			frappe.db.rollback()
			raise

	print("\n✅ All API tests passed!")
