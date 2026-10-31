# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

"""
Centralized invoice calculation engine using Python Decimal for financial precision.

All monetary arithmetic MUST go through this module to avoid floating-point
rounding errors in subtotals, discounts, taxes, and invoice totals.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


class InvoiceCalculator:
    """Stateless calculator for subscription invoice amounts.

    Every method uses Python ``Decimal`` internally and returns ``float``
    values rounded to ``PRECISION`` (2 decimal places, ``ROUND_HALF_UP``)
    so callers can store results directly in Odoo monetary fields.
    """

    PRECISION = Decimal('0.01')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_decimal(value):
        """Safely convert a value to Decimal.

        Accepts ``int``, ``float``, ``str``, and ``Decimal``.
        Returns ``Decimal('0')`` for ``None`` or falsy values.
        """
        if value is None:
            return Decimal('0')
        try:
            # Convert float → str first to avoid float-repr issues
            if isinstance(value, float):
                return Decimal(str(value))
            return Decimal(value)
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0')

    @classmethod
    def _round(cls, value):
        """Round a Decimal to 2 decimal places using ROUND_HALF_UP."""
        if not isinstance(value, Decimal):
            value = cls._to_decimal(value)
        return float(value.quantize(cls.PRECISION, rounding=ROUND_HALF_UP))

    # ------------------------------------------------------------------
    # Line-level calculations
    # ------------------------------------------------------------------

    @classmethod
    def calculate_line_subtotal(
        cls,
        quantity,
        price_unit,
        discount_type='percent',
        discount_percent=0.0,
        discount_fixed=0.0,
    ):
        """Calculate the subtotal for a single invoice line.

        Args:
            quantity: Number of units.
            price_unit: Price per unit.
            discount_type: ``'percent'`` or ``'fixed'``.
            discount_percent: Percentage discount (0-100).
            discount_fixed: Fixed monetary discount amount.

        Returns:
            float: Subtotal rounded to 2 decimal places.  Never negative.
        """
        qty = cls._to_decimal(quantity)
        price = cls._to_decimal(price_unit)
        subtotal = qty * price

        if discount_type == 'percent':
            pct = cls._to_decimal(discount_percent)
            discount_factor = Decimal('1') - pct / Decimal('100')
            subtotal = subtotal * discount_factor
        elif discount_type == 'fixed':
            fixed = cls._to_decimal(discount_fixed)
            subtotal = subtotal - fixed

        # Never allow negative subtotals
        if subtotal < Decimal('0'):
            subtotal = Decimal('0')

        return cls._round(subtotal)

    @classmethod
    def calculate_tax(cls, subtotal, tax_amount, tax_type='percent'):
        """Calculate the tax amount on a subtotal.

        Args:
            subtotal: The amount to apply tax on (after discounts).
            tax_amount: The tax rate (percentage) or fixed tax amount.
            tax_type: ``'percent'`` or ``'fixed'``.

        Returns:
            float: Tax amount rounded to 2 decimal places.
        """
        base = cls._to_decimal(subtotal)
        amount = cls._to_decimal(tax_amount)

        if tax_type == 'percent':
            tax = base * amount / Decimal('100')
        elif tax_type == 'fixed':
            tax = amount
        else:
            tax = Decimal('0')

        return cls._round(tax)

    @classmethod
    def calculate_line_taxes(cls, subtotal, taxes):
        """Calculate total tax for a line given a list of applicable taxes.

        Args:
            subtotal: Line subtotal (after discounts).
            taxes: Iterable of dicts/objects with ``amount`` and ``amount_type``
                   (or plain dicts ``{'amount': ..., 'amount_type': ...}``).

        Returns:
            tuple: (total_tax_float, list_of_tax_detail_dicts)
                   Each detail dict: ``{'tax_name', 'tax_rate', 'tax_type', 'tax_amount'}``.
        """
        total_tax = Decimal('0')
        details = []

        for tax in (taxes or []):
            if hasattr(tax, 'amount'):
                t_amount = tax.amount
                t_type = getattr(tax, 'amount_type', 'percent')
                t_name = getattr(tax, 'name', str(tax))
            elif isinstance(tax, dict):
                t_amount = tax.get('amount', 0)
                t_type = tax.get('amount_type', 'percent')
                t_name = tax.get('name', 'Tax')
            else:
                continue

            computed = cls._to_decimal(cls.calculate_tax(subtotal, t_amount, t_type))
            total_tax += computed
            details.append({
                'tax_name': str(t_name),
                'tax_rate': float(cls._to_decimal(t_amount)),
                'tax_type': t_type,
                'tax_amount': cls._round(computed),
            })

        return cls._round(total_tax), details

    # ------------------------------------------------------------------
    # Invoice-level calculations
    # ------------------------------------------------------------------

    @classmethod
    def calculate_invoice_totals(cls, lines_data):
        """Calculate full invoice totals from a list of line data dicts.

        Args:
            lines_data: List of dicts, each containing:
                - ``quantity``
                - ``price_unit``
                - ``discount_type`` (default ``'percent'``)
                - ``discount_percent`` (default ``0.0``)
                - ``discount_fixed`` (default ``0.0``)
                - ``taxes`` (list of tax dicts/objects, optional)

        Returns:
            dict with keys:
                - ``lines``: list of per-line result dicts
                - ``amount_untaxed``: float
                - ``amount_tax``: float
                - ``amount_total``: float
        """
        amount_untaxed = Decimal('0')
        amount_tax = Decimal('0')
        result_lines = []

        for line in (lines_data or []):
            subtotal = cls.calculate_line_subtotal(
                quantity=line.get('quantity', 0),
                price_unit=line.get('price_unit', 0),
                discount_type=line.get('discount_type', 'percent'),
                discount_percent=line.get('discount_percent', 0.0),
                discount_fixed=line.get('discount_fixed', 0.0),
            )

            tax_total, tax_details = cls.calculate_line_taxes(
                subtotal, line.get('taxes', []),
            )

            line_total = cls._round(cls._to_decimal(subtotal) + cls._to_decimal(tax_total))

            result_lines.append({
                'product_name': line.get('product_name', ''),
                'product_id': line.get('product_id', False),
                'quantity': float(cls._to_decimal(line.get('quantity', 0))),
                'price_unit': float(cls._to_decimal(line.get('price_unit', 0))),
                'discount_type': line.get('discount_type', 'percent'),
                'discount_percent': float(cls._to_decimal(line.get('discount_percent', 0.0))),
                'discount_fixed': float(cls._to_decimal(line.get('discount_fixed', 0.0))),
                'subtotal': subtotal,
                'tax_details': tax_details,
                'tax_total': tax_total,
                'line_total': line_total,
            })

            amount_untaxed += cls._to_decimal(subtotal)
            amount_tax += cls._to_decimal(tax_total)

        return {
            'lines': result_lines,
            'amount_untaxed': cls._round(amount_untaxed),
            'amount_tax': cls._round(amount_tax),
            'amount_total': cls._round(amount_untaxed + amount_tax),
        }

    # ------------------------------------------------------------------
    # Snapshot builder
    # ------------------------------------------------------------------

    @classmethod
    def build_calculation_snapshot(cls, lines_data, totals, currency_name=''):
        """Build a JSON string capturing the full calculation at invoice-generation time.

        This snapshot is stored on the invoice so historical calculations are
        preserved even if product prices or tax rules change later.

        Args:
            lines_data: The ``lines`` list from ``calculate_invoice_totals``.
            totals: The totals dict from ``calculate_invoice_totals``.
            currency_name: Currency code (e.g. ``'USD'``).

        Returns:
            str: JSON-encoded snapshot.
        """
        snapshot = {
            'calculation_timestamp': datetime.now(timezone.utc).isoformat(),
            'currency': currency_name,
            'lines': lines_data if isinstance(lines_data, list) else totals.get('lines', []),
            'amount_untaxed': totals.get('amount_untaxed', 0.0),
            'amount_tax': totals.get('amount_tax', 0.0),
            'amount_total': totals.get('amount_total', 0.0),
        }
        return json.dumps(snapshot, default=str, indent=2)
