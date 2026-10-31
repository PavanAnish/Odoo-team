# -*- coding: utf-8 -*-
"""Pytest configuration and stubs for environments where Odoo is not installed."""

import sys
from unittest.mock import MagicMock

if 'odoo' not in sys.modules:
    try:
        import odoo
    except ImportError:
        odoo_mock = MagicMock()
        odoo_mock._ = lambda s: s
        odoo_mock.api.depends = lambda *args: lambda fn: fn
        odoo_mock.api.model_create_multi = lambda fn: fn
        odoo_mock.api.constrains = lambda *args: lambda fn: fn
        odoo_mock.api.model = lambda fn: fn

        class MockField:
            def __init__(self, *args, **kwargs):
                pass

        for field_type in [
            'Boolean', 'Char', 'Integer', 'Float', 'Monetary',
            'Date', 'Datetime', 'Text', 'Html', 'Selection',
            'Many2one', 'One2many', 'Many2many',
        ]:
            setattr(odoo_mock.fields, field_type, MockField)

        class MockModel:
            _name = None
            _description = None
            _inherit = None
            _order = None

            def __init__(self, *args, **kwargs):
                pass

        odoo_mock.models.Model = MockModel
        odoo_mock.models.AbstractModel = MockModel
        odoo_mock.models.TransientModel = MockModel

        class UserError(Exception):
            pass

        class ValidationError(Exception):
            pass

        odoo_mock.exceptions.UserError = UserError
        odoo_mock.exceptions.ValidationError = ValidationError

        import unittest
        class MockTransactionCase(unittest.TestCase):
            pass

        odoo_mock.tests.common.TransactionCase = MockTransactionCase
        odoo_mock.tests.common.tagged = lambda *args: lambda cls: cls

        sys.modules['odoo'] = odoo_mock
        sys.modules['odoo.api'] = odoo_mock.api
        sys.modules['odoo.fields'] = odoo_mock.fields
        sys.modules['odoo.models'] = odoo_mock.models
        sys.modules['odoo.exceptions'] = odoo_mock.exceptions
        sys.modules['odoo.tests'] = odoo_mock.tests
        sys.modules['odoo.tests.common'] = odoo_mock.tests.common
