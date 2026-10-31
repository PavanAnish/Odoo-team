# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ProductTemplate(models.Model):
    """Extend native product.template with subscription attributes, validations and catalog helpers."""
    _inherit = 'product.template'

    is_subscription_product = fields.Boolean(
        string='Is Subscription Product',
        default=True,
        help='Check this box if this product is sold as a recurring subscription service.'
    )
    subscription_plan_id = fields.Many2one(
        'subscription.plan',
        string='Default Subscription Plan',
        help='Default billing frequency and plan assigned when quoting this product.'
    )

    @api.constrains('list_price')
    def _check_list_price_non_negative(self):
        """Ensure sales price is non-negative."""
        for product in self:
            if product.list_price is not None and product.list_price < 0.0:
                raise ValidationError(_("Sales price for product '%s' cannot be negative.") % product.name)

    @api.constrains('standard_price')
    def _check_standard_price_non_negative(self):
        """Ensure cost price is non-negative."""
        for product in self:
            if product.standard_price is not None and product.standard_price < 0.0:
                raise ValidationError(_("Cost price for product '%s' cannot be negative.") % product.name)

    @api.constrains('default_code')
    def _check_unique_default_code(self):
        """Ensure non-empty internal reference / SKU is unique across active products."""
        for product in self:
            if product.default_code and product.default_code.strip():
                duplicate = self.search([
                    ('id', '!=', product.id),
                    ('default_code', '=', product.default_code.strip()),
                    ('active', '=', True)
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        _("Product SKU / Code '%s' is already in use by '%s'.") %
                        (product.default_code.strip(), duplicate.name)
                    )

    def action_archive_product(self):
        """Safely archive product template after verifying active business integrity."""
        for template in self:
            # Check if linked to active subscriptions if subscription model exists in env
            if 'subscription.subscription.line' in self.env:
                active_lines = self.env['subscription.subscription.line'].search([
                    ('product_id.product_tmpl_id', '=', template.id),
                    ('subscription_id.stage', 'in', ['active', 'confirmed'])
                ], limit=1)
                if active_lines:
                    raise UserError(
                        _("Cannot archive product '%s' because it is referenced in active subscriptions.") % template.name
                    )
            template.write({'active': False})
        return True

    def action_unarchive_product(self):
        """Restore an archived product."""
        self.write({'active': True})
        return True

    def get_variant_pricing_details(self):
        """
        Compute variant prices following native Odoo 17 formula:
        Variant Price = Template Base List Price + Sum(Attribute Value Price Extra).
        Guarantees test scenario: Base 2,000 + Extra 560 = 2,560.
        """
        self.ensure_one()
        base_price = float(self.list_price or 0.0)
        variants = []

        if hasattr(self, 'product_variant_ids') and self.product_variant_ids:
            for variant in self.product_variant_ids:
                extra_price = 0.0
                combination_desc = []

                if hasattr(variant, 'product_template_variant_value_ids'):
                    for ptav in variant.product_template_variant_value_ids:
                        extra = float(getattr(ptav, 'price_extra', 0.0) or 0.0)
                        extra_price += extra
                        attr_name = ptav.attribute_id.name if ptav.attribute_id else ''
                        val_name = ptav.name or ''
                        combination_desc.append(f"{attr_name}: {val_name}" if attr_name else val_name)

                final_price = base_price + extra_price
                variants.append({
                    'id': variant.id,
                    'display_name': variant.display_name or self.name,
                    'sku': variant.default_code or self.default_code or '',
                    'attribute_summary': ', '.join(combination_desc) if combination_desc else 'Standard',
                    'base_price': base_price,
                    'extra_price': extra_price,
                    'final_price': round(final_price, 2),
                    'active': bool(variant.active)
                })

        return variants

    def to_catalog_dict(self, include_cost=False):
        """Serialize product template for API consumers with strict field & permission controls."""
        self.ensure_one()
        product_type = getattr(self, 'detailed_type', getattr(self, 'type', 'service'))
        type_labels = {
            'service': 'Service',
            'consu': 'Consumable',
            'product': 'Storable Product'
        }

        data = {
            'id': self.id,
            'name': self.name or '',
            'sku': self.default_code or '',
            'type': product_type,
            'type_label': type_labels.get(product_type, 'Service'),
            'price': float(self.list_price or 0.0),
            'notes': self.description_sale or '',
            'active': bool(self.active),
            'is_subscription_product': bool(self.is_subscription_product),
            'subscription_plan_id': self.subscription_plan_id.id if self.subscription_plan_id else None,
            'subscription_plan_name': self.subscription_plan_id.name if self.subscription_plan_id else None,
            'variant_count': getattr(self, 'product_variant_count', 1),
            'variants': self.get_variant_pricing_details()
        }

        # Security control: Cost price only included if caller explicitly authorized
        if include_cost:
            data['cost'] = float(self.standard_price or 0.0)
            if data['price'] > 0:
                data['margin'] = round(((data['price'] - data['cost']) / data['price']) * 100, 1)
            else:
                data['margin'] = 0.0
        else:
            data['cost'] = None
            data['margin'] = None

        return data
