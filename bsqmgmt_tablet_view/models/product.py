# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    material_type = fields.Selection([
        ('source', 'Source Material'),
        ('inventory', 'Inventory')], string='Material Type')
