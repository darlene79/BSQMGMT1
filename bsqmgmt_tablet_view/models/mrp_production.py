# -*- coding: utf-8 -*-

from odoo.tools import float_compare, float_round
from odoo import api, fields, models, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    source_weight_lbs = fields.Float('Source Weight (lbs)', compute='_compute_source_weight_lbs')
    end_weight_lbs = fields.Float('End Weight (lbs)', compute='_compute_end_weight_lbs')
    yields = fields.Float('Yield (%)', compute='_compute_yields')

    @api.depends('move_raw_ids')
    def _compute_source_weight_lbs(self):
        for wo in self:
            wo.source_weight_lbs = 0.0
            for line in wo.move_raw_ids.filtered(lambda x: x.product_id.material_type == 'source'):
                wo.source_weight_lbs += line.quantity_done

    @api.depends('finished_move_line_ids')
    def _compute_end_weight_lbs(self):
        for wo in self:
            wo.end_weight_lbs = 0.0
            for line in wo.finished_move_line_ids.filtered(lambda x: x.lot_id):
                wo.end_weight_lbs += line.qty_done

    @api.depends('source_weight_lbs', 'end_weight_lbs')
    def _compute_yields(self):
        for wo in self:
            if float_compare(wo.source_weight_lbs, 0, precision_digits=100) > 0:
                wo.yields = wo.end_weight_lbs / wo.source_weight_lbs
            else:
                wo.yields = 0.0
