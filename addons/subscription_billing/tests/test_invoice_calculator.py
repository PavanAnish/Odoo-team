# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

"""
Pure-Python unit tests for InvoiceCalculator.

These tests validate Decimal precision, rounding, discount types, tax
computation, and snapshot generation WITHOUT any Odoo dependency so they
can run with ``python -m pytest`` or ``python -m unittest``.
"""

import json
import unittest
from decimal import Decimal

# Import the calculator — works whether run standalone or via Odoo test runner.
try:
    from odoo.addons.subscription_billing.models.invoice_calculator import InvoiceCalculator
except ImportError:
    import sys
    import os
    # Allow running directly: add the models directory to the path.
    _models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    if _models_dir not in sys.path:
        sys.path.insert(0, os.path.abspath(_models_dir))
    from invoice_calculator import InvoiceCalculator


class TestInvoiceCalculatorSubtotal(unittest.TestCase):
    """Test line subtotal calculations."""

    def test_basic_subtotal(self):
        """quantity × price_unit with no discount."""
        result = InvoiceCalculator.calculate_line_subtotal(3, 100.0)
        self.assertEqual(result, 300.0)

    def test_zero_quantity(self):
        result = InvoiceCalculator.calculate_line_subtotal(0, 50.0)
        self.assertEqual(result, 0.0)

    def test_zero_price(self):
        result = InvoiceCalculator.calculate_line_subtotal(5, 0.0)
        self.assertEqual(result, 0.0)

    def test_percentage_discount(self):
        """10% discount on $100 × 2 = $180."""
        result = InvoiceCalculator.calculate_line_subtotal(
            2, 100.0, discount_type='percent', discount_percent=10.0,
        )
        self.assertEqual(result, 180.0)

    def test_percentage_discount_100_percent(self):
        """100% discount → $0."""
        result = InvoiceCalculator.calculate_line_subtotal(
            5, 200.0, discount_type='percent', discount_percent=100.0,
        )
        self.assertEqual(result, 0.0)

    def test_fixed_discount(self):
        """$15 fixed discount on $100 × 1 = $85."""
        result = InvoiceCalculator.calculate_line_subtotal(
            1, 100.0, discount_type='fixed', discount_fixed=15.0,
        )
        self.assertEqual(result, 85.0)

    def test_fixed_discount_larger_than_subtotal(self):
        """Fixed discount exceeding subtotal → clamped to $0."""
        result = InvoiceCalculator.calculate_line_subtotal(
            1, 50.0, discount_type='fixed', discount_fixed=100.0,
        )
        self.assertEqual(result, 0.0)

    def test_none_values_treated_as_zero(self):
        result = InvoiceCalculator.calculate_line_subtotal(None, None)
        self.assertEqual(result, 0.0)

    def test_string_number_inputs(self):
        """Calculator should handle string representations of numbers."""
        result = InvoiceCalculator.calculate_line_subtotal('3', '33.33')
        self.assertEqual(result, 99.99)


class TestInvoiceCalculatorTax(unittest.TestCase):
    """Test tax calculations."""

    def test_percentage_tax(self):
        """18% tax on $100 = $18."""
        result = InvoiceCalculator.calculate_tax(100.0, 18.0, 'percent')
        self.assertEqual(result, 18.0)

    def test_fixed_tax(self):
        """Fixed tax of $5."""
        result = InvoiceCalculator.calculate_tax(100.0, 5.0, 'fixed')
        self.assertEqual(result, 5.0)

    def test_zero_tax(self):
        result = InvoiceCalculator.calculate_tax(100.0, 0.0, 'percent')
        self.assertEqual(result, 0.0)

    def test_tax_on_zero_subtotal(self):
        result = InvoiceCalculator.calculate_tax(0.0, 18.0, 'percent')
        self.assertEqual(result, 0.0)

    def test_unknown_tax_type(self):
        """Unknown tax types produce zero tax."""
        result = InvoiceCalculator.calculate_tax(100.0, 18.0, 'unknown')
        self.assertEqual(result, 0.0)


class TestInvoiceCalculatorLineTaxes(unittest.TestCase):
    """Test line tax calculations with multiple taxes."""

    def test_single_percent_tax(self):
        total, details = InvoiceCalculator.calculate_line_taxes(
            100.0, [{'amount': 18.0, 'amount_type': 'percent', 'name': 'GST 18%'}],
        )
        self.assertEqual(total, 18.0)
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]['tax_name'], 'GST 18%')
        self.assertEqual(details[0]['tax_amount'], 18.0)

    def test_multiple_taxes(self):
        """Two taxes: 10% + $5 fixed."""
        total, details = InvoiceCalculator.calculate_line_taxes(200.0, [
            {'amount': 10.0, 'amount_type': 'percent', 'name': 'VAT 10%'},
            {'amount': 5.0, 'amount_type': 'fixed', 'name': 'Eco Tax'},
        ])
        # 10% of 200 = 20, fixed 5 = 5, total = 25
        self.assertEqual(total, 25.0)
        self.assertEqual(len(details), 2)

    def test_no_taxes(self):
        total, details = InvoiceCalculator.calculate_line_taxes(100.0, [])
        self.assertEqual(total, 0.0)
        self.assertEqual(details, [])

    def test_none_taxes(self):
        total, details = InvoiceCalculator.calculate_line_taxes(100.0, None)
        self.assertEqual(total, 0.0)
        self.assertEqual(details, [])


class TestInvoiceCalculatorTotals(unittest.TestCase):
    """Test full invoice total calculation."""

    def test_single_line_no_discount_no_tax(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 5,
            'price_unit': 20.0,
        }])
        self.assertEqual(totals['amount_untaxed'], 100.0)
        self.assertEqual(totals['amount_tax'], 0.0)
        self.assertEqual(totals['amount_total'], 100.0)
        self.assertEqual(len(totals['lines']), 1)

    def test_single_line_with_percent_discount(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 1,
            'price_unit': 100.0,
            'discount_type': 'percent',
            'discount_percent': 10.0,
        }])
        self.assertEqual(totals['amount_untaxed'], 90.0)
        self.assertEqual(totals['amount_total'], 90.0)

    def test_single_line_with_fixed_discount(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 1,
            'price_unit': 100.0,
            'discount_type': 'fixed',
            'discount_fixed': 15.0,
        }])
        self.assertEqual(totals['amount_untaxed'], 85.0)
        self.assertEqual(totals['amount_total'], 85.0)

    def test_single_line_with_tax(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 1,
            'price_unit': 100.0,
            'taxes': [{'amount': 18.0, 'amount_type': 'percent', 'name': 'GST'}],
        }])
        self.assertEqual(totals['amount_untaxed'], 100.0)
        self.assertEqual(totals['amount_tax'], 18.0)
        self.assertEqual(totals['amount_total'], 118.0)

    def test_single_line_with_discount_and_tax(self):
        """10% discount + 18% tax on $100."""
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 1,
            'price_unit': 100.0,
            'discount_type': 'percent',
            'discount_percent': 10.0,
            'taxes': [{'amount': 18.0, 'amount_type': 'percent', 'name': 'GST'}],
        }])
        # Subtotal: 100 * 0.9 = 90
        # Tax: 90 * 0.18 = 16.20
        # Total: 90 + 16.20 = 106.20
        self.assertEqual(totals['amount_untaxed'], 90.0)
        self.assertEqual(totals['amount_tax'], 16.20)
        self.assertEqual(totals['amount_total'], 106.20)

    def test_multiple_lines(self):
        """3 lines with different prices, quantities, discounts, and taxes."""
        totals = InvoiceCalculator.calculate_invoice_totals([
            {
                'product_name': 'Product A',
                'quantity': 2,
                'price_unit': 50.0,
                # No discount, no tax → subtotal 100
            },
            {
                'product_name': 'Product B',
                'quantity': 1,
                'price_unit': 200.0,
                'discount_type': 'percent',
                'discount_percent': 25.0,
                # 25% discount → subtotal 150
                'taxes': [{'amount': 10.0, 'amount_type': 'percent', 'name': 'Tax 10%'}],
                # Tax: 150 * 0.10 = 15
            },
            {
                'product_name': 'Product C',
                'quantity': 3,
                'price_unit': 33.33,
                'discount_type': 'fixed',
                'discount_fixed': 10.0,
                # subtotal = 3 * 33.33 - 10 = 99.99 - 10 = 89.99
                'taxes': [
                    {'amount': 5.0, 'amount_type': 'percent', 'name': 'Tax 5%'},
                    {'amount': 2.0, 'amount_type': 'fixed', 'name': 'Eco Fee'},
                ],
                # Tax: 89.99 * 0.05 = 4.50 (rounded) + 2.00 = 6.50
            },
        ])
        # Line totals:
        #   A: untaxed=100, tax=0, total=100
        #   B: untaxed=150, tax=15, total=165
        #   C: untaxed=89.99, tax=6.50, total=96.49
        self.assertEqual(totals['amount_untaxed'], 339.99)
        self.assertEqual(totals['amount_tax'], 21.50)
        self.assertEqual(totals['amount_total'], 361.49)
        self.assertEqual(len(totals['lines']), 3)

    def test_empty_lines(self):
        totals = InvoiceCalculator.calculate_invoice_totals([])
        self.assertEqual(totals['amount_untaxed'], 0.0)
        self.assertEqual(totals['amount_tax'], 0.0)
        self.assertEqual(totals['amount_total'], 0.0)

    def test_none_lines(self):
        totals = InvoiceCalculator.calculate_invoice_totals(None)
        self.assertEqual(totals['amount_total'], 0.0)


class TestDecimalPrecisionAndRounding(unittest.TestCase):
    """Test that Decimal arithmetic avoids float rounding errors."""

    def test_repeating_decimal_multiplication(self):
        """$33.33 × 3 must equal $99.99, not $100.00 or $99.98999..."""
        result = InvoiceCalculator.calculate_line_subtotal(3, 33.33)
        self.assertEqual(result, 99.99)

    def test_round_half_up_behavior(self):
        """Verify ROUND_HALF_UP: 0.005 rounds up to 0.01."""
        # 1 × 10.005 = 10.005 → should round to 10.01 (ROUND_HALF_UP)
        result = InvoiceCalculator.calculate_line_subtotal(1, 10.005)
        self.assertEqual(result, 10.01)

    def test_tax_rounding(self):
        """Tax on $89.99 at 5% = $4.4995 → rounds to $4.50."""
        result = InvoiceCalculator.calculate_tax(89.99, 5.0, 'percent')
        self.assertEqual(result, 4.50)

    def test_large_numbers(self):
        """Large monetary values still compute correctly."""
        result = InvoiceCalculator.calculate_line_subtotal(1000, 999999.99)
        self.assertEqual(result, 999999990.0)

    def test_many_decimal_places_input(self):
        """Inputs with many decimal places are handled gracefully."""
        result = InvoiceCalculator.calculate_line_subtotal(1, 99.999999999)
        self.assertEqual(result, 100.0)  # Rounded to 2 dp

    def test_percent_discount_precision(self):
        """33.33% discount on $100 = $66.67 (not $66.66999... or $66.68)."""
        result = InvoiceCalculator.calculate_line_subtotal(
            1, 100.0, discount_type='percent', discount_percent=33.33,
        )
        self.assertEqual(result, 66.67)


class TestCalculationSnapshot(unittest.TestCase):
    """Test snapshot building."""

    def test_snapshot_is_valid_json(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 1, 'price_unit': 100.0,
        }])
        snapshot = InvoiceCalculator.build_calculation_snapshot(
            totals['lines'], totals, currency_name='USD',
        )
        parsed = json.loads(snapshot)
        self.assertEqual(parsed['currency'], 'USD')
        self.assertEqual(parsed['amount_total'], 100.0)
        self.assertIn('calculation_timestamp', parsed)
        self.assertEqual(len(parsed['lines']), 1)

    def test_snapshot_preserves_discount_details(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 2,
            'price_unit': 50.0,
            'discount_type': 'fixed',
            'discount_fixed': 10.0,
        }])
        snapshot = InvoiceCalculator.build_calculation_snapshot(
            totals['lines'], totals, currency_name='EUR',
        )
        parsed = json.loads(snapshot)
        line = parsed['lines'][0]
        self.assertEqual(line['discount_type'], 'fixed')
        self.assertEqual(line['discount_fixed'], 10.0)
        self.assertEqual(line['subtotal'], 90.0)

    def test_snapshot_preserves_tax_details(self):
        totals = InvoiceCalculator.calculate_invoice_totals([{
            'quantity': 1,
            'price_unit': 100.0,
            'taxes': [{'amount': 18.0, 'amount_type': 'percent', 'name': 'GST 18%'}],
        }])
        snapshot = InvoiceCalculator.build_calculation_snapshot(
            totals['lines'], totals, currency_name='INR',
        )
        parsed = json.loads(snapshot)
        line = parsed['lines'][0]
        self.assertEqual(len(line['tax_details']), 1)
        self.assertEqual(line['tax_details'][0]['tax_name'], 'GST 18%')
        self.assertEqual(line['tax_details'][0]['tax_amount'], 18.0)
        self.assertEqual(parsed['amount_tax'], 18.0)


if __name__ == '__main__':
    unittest.main()
