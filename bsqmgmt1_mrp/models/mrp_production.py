# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.tools import float_compare, float_round

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    source_weight_lbs = fields.Float(string='Source Weight (lbs)', compute='_compute_source_weight_lbs')
    end_weight_lbs = fields.Float(string='End Weight (lbs)', compute='_compute_end_weight_lbs')
    yields = fields.Float(string='Yields', compute='_compute_yields')

    @api.depends('source_weight_lbs', 'end_weight_lbs')
    def _compute_yields(self):
        for s in self:
            if float_compare(s.source_weight_lbs, 0.0) > 0:
                s.yields = s.end_weight_lbs / s.source_weight_lbs
            else:
                s.yields = 0.0
    

    @api.depends('finished_move_line_ids')
    def _compute_end_weight_lbs(self):
        for s in self:
            for f in s.finished_move_line_ids.filtered(lambda x: x.lot_id):
                s.end_weight_lbs += f.qty_done

    @api.depends('move_raw_ids')
    def _compute_source_weight_lbs(self):
        for s in self:
            for f in s.move_raw_ids:
                s.source_weight_lbs += f.quantity_done