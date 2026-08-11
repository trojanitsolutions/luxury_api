import sys
from frappe.utils import flt


def run():
	"""Verify _prorate_payments enforces negative signs for return invoices."""
	from luxury_api.api.sales_invoice_pos import _prorate_payments as _prorate_payments_si
	from luxury_api.api.pos_invoice import _prorate_payments as _prorate_payments_pi

	precision = 2
	multiplier = 100

	# Test 1: Normal case (positive ratio, original amounts already negative)
	payments_original = [
		{"amount": -100.0, "base_amount": -100.0, "mode_of_payment": "Cash", "type": "Pay", "account": None, "default": 1},
		{"amount": -50.0, "base_amount": -50.0, "mode_of_payment": "Card", "type": "Pay", "account": None, "default": 0},
	]
	ratio = 0.5  # Return 50% of items
	prorated = _prorate_payments_si(payments_original, ratio, precision)
	assert len(prorated) == 2, f"Expected 2 rows, got {len(prorated)}"
	total = sum(flt(p["amount"]) for p in prorated)
	expected_total = -75.0  # (-100 - 50) * 0.5
	assert abs(total - expected_total) < 0.01, f"Expected total {expected_total}, got {total}"
	assert all(flt(p["amount"]) <= 0 for p in prorated), f"Not all amounts are <= 0: {prorated}"
	print(f"✓ Test 1 (normal case): ratio={ratio}, total={total}")

	# Test 2: Negative ratio (simulating fixed-charge sign flip)
	ratio = -0.5  # Simulated sign flip from fixed/Actual tax charge
	prorated = _prorate_payments_pi(payments_original, ratio, precision)
	assert len(prorated) == 2, f"Expected 2 rows, got {len(prorated)}"
	total = sum(flt(p["amount"]) for p in prorated)
	expected_total = 75.0  # (-100 - 50) * -0.5 = 75.0 before sign enforcement
	assert all(flt(p["amount"]) <= 0 for p in prorated), f"Amounts must be negative even with negative ratio: {prorated}"
	print(f"✓ Test 2 (negative ratio, sign enforced): ratio={ratio}, total={sum(flt(p['amount']) for p in prorated)}")

	# Test 3: Zero ratio (fully-discounted partial return)
	ratio = 0
	prorated = _prorate_payments_si(payments_original, ratio, precision)
	assert len(prorated) == 2, f"Expected 2 rows, got {len(prorated)}"
	total = sum(flt(p["amount"]) for p in prorated)
	assert abs(total) < 0.01, f"Expected total ~0, got {total}"
	assert all(flt(p["amount"]) == 0 for p in prorated), f"All amounts should be 0 when ratio=0: {prorated}"
	print(f"✓ Test 3 (ratio=0, all zeros): total={total}")

	print("\n✅ All checks passed. _prorate_payments correctly enforces negative signs.")


if __name__ == "__main__":
	run()
