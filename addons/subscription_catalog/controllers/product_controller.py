# -*- coding: utf-8 -*-
# Part of Odoo Subscription Management System.

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request, route


class ProductCatalogController(http.Controller):
    """
    Production-grade HTTP JSON controller for Subscription Product Catalog.
    Provides authenticated, authorized CRUD and variant pricing operations
    for the custom Admin Panel and external integrations.
    """

    def _check_auth_and_permissions(self):
        """
        Validate session authentication and return role flags.
        Enforces that unauthenticated sessions receive a 401 error.
        """
        if not request.env.user or request.env.user._is_public():
            raise AccessError(_("Authentication required to access product catalog."))

        is_manager = request.env.user.has_group('subscription_base.group_subscription_manager')
        is_user = request.env.user.has_group('subscription_base.group_subscription_user') or is_manager

        if not is_user:
            raise AccessError(_("Insufficient permissions to view or manage subscription products."))

        return {
            'can_view_cost': is_manager,
            'can_edit': is_manager,
            'is_manager': is_manager
        }

    # -------------------------------------------------------------------------
    # 1. Product Listing
    # -------------------------------------------------------------------------
    @route('/subscription/catalog/products/list', type='json', auth='user', methods=['POST'], csrf=False)
    def list_products(self, search=None, product_type=None, active_filter='active',
                      sort_by='name', sort_dir='asc', page=1, limit=50, **kwargs):
        """
        Retrieve paginated, filtered, and sorted subscription products.
        Cost price and profit margins are strictly omitted unless the user is a manager.
        """
        try:
            perms = self._check_auth_and_permissions()
            ProductTemplate = request.env['product.template']

            domain = [('is_subscription_product', '=', True)]

            # Filter active / archived
            if active_filter == 'active':
                domain.append(('active', '=', True))
            elif active_filter == 'archived':
                domain.append(('active', '=', False))
            # 'all' includes both active and archived

            # Filter product type
            if product_type in ['service', 'consu']:
                domain.append(('detailed_type', '=', product_type))

            # Server-side search on name or default_code (SKU)
            if search and search.strip():
                term = search.strip()
                domain.extend(['|', ('name', 'ilike', term), ('default_code', 'ilike', term)])

            total_count = ProductTemplate.search_count(domain)

            # Order specification
            allowed_sort_fields = {'name', 'list_price', 'default_code', 'create_date', 'id'}
            sort_field = sort_by if sort_by in allowed_sort_fields else 'name'
            direction = 'desc' if str(sort_dir).lower() == 'desc' else 'asc'
            order = f"{sort_field} {direction}"

            page = max(1, int(page or 1))
            limit = min(100, max(1, int(limit or 50)))
            offset = (page - 1) * limit

            products = ProductTemplate.search(domain, order=order, limit=limit, offset=offset)
            serialized = [p.to_catalog_dict(include_cost=perms['can_view_cost']) for p in products]

            return {
                'status': 'success',
                'total': total_count,
                'page': page,
                'limit': limit,
                'can_view_cost': perms['can_view_cost'],
                'can_edit': perms['can_edit'],
                'products': serialized
            }
        except AccessError as e:
            return {'status': 'error', 'error_type': 'access_denied', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'error_type': 'server_error', 'message': str(e)}

    # -------------------------------------------------------------------------
    # 2. Product Details
    # -------------------------------------------------------------------------
    @route('/subscription/catalog/products/get', type='json', auth='user', methods=['POST'], csrf=False)
    def get_product_details(self, product_id, **kwargs):
        """Retrieve full details for a single product template by ID."""
        try:
            perms = self._check_auth_and_permissions()
            product = request.env['product.template'].browse(int(product_id))

            if not product.exists():
                return {'status': 'error', 'error_type': 'not_found', 'message': _("Product not found.")}

            return {
                'status': 'success',
                'can_view_cost': perms['can_view_cost'],
                'can_edit': perms['can_edit'],
                'product': product.to_catalog_dict(include_cost=perms['can_view_cost'])
            }
        except AccessError as e:
            return {'status': 'error', 'error_type': 'access_denied', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'error_type': 'server_error', 'message': str(e)}

    # -------------------------------------------------------------------------
    # 3. Create Product
    # -------------------------------------------------------------------------
    @route('/subscription/catalog/products/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_product(self, name, list_price, detailed_type='service', default_code=None,
                       standard_price=0.0, description_sale=None, variants=None, **kwargs):
        """
        Create a new subscription product with server-side field and permission validation.
        Only users with manager privileges can create products.
        """
        try:
            perms = self._check_auth_and_permissions()
            if not perms['can_edit']:
                raise AccessError(_("You do not have permission to create subscription products."))

            # Validation
            if not name or not str(name).strip():
                raise ValidationError(_("Product name is required."))

            try:
                list_price = float(list_price)
                if list_price < 0.0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError(_("Sales price must be a non-negative number."))

            try:
                standard_price = float(standard_price or 0.0)
                if standard_price < 0.0:
                    raise ValueError()
            except (ValueError, TypeError):
                raise ValidationError(_("Cost price must be a non-negative number."))

            if detailed_type not in ['service', 'consu']:
                detailed_type = 'service'

            vals = {
                'name': str(name).strip(),
                'list_price': list_price,
                'standard_price': standard_price,
                'detailed_type': detailed_type,
                'default_code': str(default_code).strip() if default_code else False,
                'description_sale': str(description_sale).strip() if description_sale else False,
                'is_subscription_product': True,
                'active': True
            }

            product = request.env['product.template'].create(vals)

            # Configure variants if attributes/values provided
            if variants and isinstance(variants, list):
                self._apply_variants_config(product, variants)

            return {
                'status': 'success',
                'message': _("Product '%s' created successfully.") % product.name,
                'product': product.to_catalog_dict(include_cost=True)
            }
        except (ValidationError, UserError) as e:
            return {'status': 'error', 'error_type': 'validation_error', 'message': str(e)}
        except AccessError as e:
            return {'status': 'error', 'error_type': 'access_denied', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'error_type': 'server_error', 'message': str(e)}

    # -------------------------------------------------------------------------
    # 4. Update Product
    # -------------------------------------------------------------------------
    @route('/subscription/catalog/products/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_product(self, product_id, **kwargs):
        """Update existing product template fields."""
        try:
            perms = self._check_auth_and_permissions()
            if not perms['can_edit']:
                raise AccessError(_("You do not have permission to edit subscription products."))

            product = request.env['product.template'].browse(int(product_id))
            if not product.exists():
                return {'status': 'error', 'error_type': 'not_found', 'message': _("Product not found.")}

            allowed_fields = ['name', 'list_price', 'standard_price', 'detailed_type', 'default_code', 'description_sale']
            vals = {}

            if 'name' in kwargs:
                if not str(kwargs['name']).strip():
                    raise ValidationError(_("Product name cannot be empty."))
                vals['name'] = str(kwargs['name']).strip()

            if 'list_price' in kwargs:
                try:
                    price = float(kwargs['list_price'])
                    if price < 0.0:
                        raise ValueError()
                    vals['list_price'] = price
                except (ValueError, TypeError):
                    raise ValidationError(_("Sales price must be non-negative."))

            if 'standard_price' in kwargs:
                try:
                    cost = float(kwargs['standard_price'])
                    if cost < 0.0:
                        raise ValueError()
                    vals['standard_price'] = cost
                except (ValueError, TypeError):
                    raise ValidationError(_("Cost price must be non-negative."))

            if 'detailed_type' in kwargs and kwargs['detailed_type'] in ['service', 'consu']:
                vals['detailed_type'] = kwargs['detailed_type']

            if 'default_code' in kwargs:
                vals['default_code'] = str(kwargs['default_code']).strip() if kwargs['default_code'] else False

            if 'description_sale' in kwargs:
                vals['description_sale'] = str(kwargs['description_sale']).strip() if kwargs['description_sale'] else False

            if vals:
                product.write(vals)

            if 'variants' in kwargs and isinstance(kwargs['variants'], list):
                self._apply_variants_config(product, kwargs['variants'])

            return {
                'status': 'success',
                'message': _("Product updated successfully."),
                'product': product.to_catalog_dict(include_cost=True)
            }
        except (ValidationError, UserError) as e:
            return {'status': 'error', 'error_type': 'validation_error', 'message': str(e)}
        except AccessError as e:
            return {'status': 'error', 'error_type': 'access_denied', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'error_type': 'server_error', 'message': str(e)}

    # -------------------------------------------------------------------------
    # 5. Archive & Unarchive
    # -------------------------------------------------------------------------
    @route('/subscription/catalog/products/archive', type='json', auth='user', methods=['POST'], csrf=False)
    def archive_product(self, product_id, **kwargs):
        """Archive a product record safely."""
        try:
            perms = self._check_auth_and_permissions()
            if not perms['can_edit']:
                raise AccessError(_("You do not have permission to archive products."))

            product = request.env['product.template'].browse(int(product_id))
            if not product.exists():
                return {'status': 'error', 'error_type': 'not_found', 'message': _("Product not found.")}

            product.action_archive_product()
            return {
                'status': 'success',
                'message': _("Product '%s' archived successfully.") % product.name
            }
        except (ValidationError, UserError) as e:
            return {'status': 'error', 'error_type': 'validation_error', 'message': str(e)}
        except AccessError as e:
            return {'status': 'error', 'error_type': 'access_denied', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'error_type': 'server_error', 'message': str(e)}

    @route('/subscription/catalog/products/unarchive', type='json', auth='user', methods=['POST'], csrf=False)
    def unarchive_product(self, product_id, **kwargs):
        """Restore an archived product."""
        try:
            perms = self._check_auth_and_permissions()
            if not perms['can_edit']:
                raise AccessError(_("You do not have permission to unarchive products."))

            product = request.env['product.template'].browse(int(product_id))
            if not product.exists():
                return {'status': 'error', 'error_type': 'not_found', 'message': _("Product not found.")}

            product.action_unarchive_product()
            return {
                'status': 'success',
                'message': _("Product '%s' restored successfully.") % product.name
            }
        except Exception as e:
            return {'status': 'error', 'error_type': 'server_error', 'message': str(e)}

    # -------------------------------------------------------------------------
    # Helper: Apply Variant Configuration
    # -------------------------------------------------------------------------
    def _apply_variants_config(self, template, variant_list):
        """
        Configure attributes and variant lines using Odoo ORM.
        Avoids duplicate attributes and respects native price_extra.
        """
        Attribute = request.env['product.attribute']
        AttributeValue = request.env['product.attribute.value']

        for item in variant_list:
            attr_name = item.get('attribute_name') or item.get('a')
            if not attr_name or not str(attr_name).strip():
                continue

            attr_name = str(attr_name).strip()
            # If formatted like 'Brand: Odoo', split name and value
            if ':' in attr_name:
                parts = attr_name.split(':', 1)
                attr_label = parts[0].strip()
                val_label = parts[1].strip()
            else:
                attr_label = 'Option'
                val_label = attr_name

            attribute = Attribute.search([('name', '=', attr_label)], limit=1)
            if not attribute:
                attribute = Attribute.create({'name': attr_label})

            value = AttributeValue.search([
                ('attribute_id', '=', attribute.id),
                ('name', '=', val_label)
            ], limit=1)
            if not value:
                value = AttributeValue.create({
                    'name': val_label,
                    'attribute_id': attribute.id
                })

            # Check if template attribute line already exists
            line = template.attribute_line_ids.filtered(lambda l: l.attribute_id.id == attribute.id)
            if not line:
                template.attribute_line_ids = [(0, 0, {
                    'attribute_id': attribute.id,
                    'value_ids': [(4, value.id)]
                })]
            else:
                if value.id not in line.value_ids.ids:
                    line.value_ids = [(4, value.id)]

            # Configure price_extra if provided
            extra_price = float(item.get('price_extra', item.get('x', 0.0)) or 0.0)
            if extra_price and hasattr(template, 'attribute_line_ids'):
                ptav = request.env['product.template.attribute.value'].search([
                    ('product_tmpl_id', '=', template.id),
                    ('product_attribute_value_id', '=', value.id)
                ], limit=1)
                if ptav:
                    ptav.price_extra = extra_price
