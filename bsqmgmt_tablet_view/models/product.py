# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    material_type = fields.Selection([
        ('source', 'Source Material'),
        ('inventory', 'Inventory')], string='Material Type')

class ProductProduct(models.Model):
    _inherit = 'product.product'

    material_type = fields.Selection([
        ('source', 'Source Material'),
        ('inventory', 'Inventory')], string='Material Type')
