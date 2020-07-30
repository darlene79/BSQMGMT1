# -*- coding: utf-8 -*-
from collections import defaultdict
from datetime import datetime

from odoo.tools import float_compare, float_round
from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api, _


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    initial_qty_remaining = fields.Float(compute='_compute_initial_qty', digits='Product Unit of Measure', stored=True)
    initial_component_remaining_qty = fields.Float(compute='_compute_initial_qty', digits='Product Unit of Measure', stored=True)

    def open_tablet_view(self):
        self.ensure_one()
        if not self.is_user_working and self.working_state != 'blocked' and self.state in ('ready', 'progress'):
            self.button_start()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'views': [[self.env.ref('mrp_workorder.mrp_workorder_view_form_tablet').id, 'form']],
            'res_id': self.id,
            'target': 'fullscreen',
            'flags': {
                'withControlPanel': False,
                'form_view_initial_mode': 'edit',
            },
            'context': {'tablet_view': True}
        }

    def _next(self, continue_production=False):
        """tablet view action modified to allow user to set qty_producing
        to a number greater than qty_remaining
        removed modification of component_remaining_qty"""

        self.ensure_one()
        rounding = self.product_uom_id.rounding

        if float_compare(self.qty_producing, 0, precision_rounding=rounding) < 0:
            raise UserError(
                _('Please ensure the quantity to produce is nonnegative.'))
        elif self.test_type in ('register_byproducts', 'register_consumed_materials'):
            if self.component_tracking != 'none' and not self.lot_id and self.qty_done != 0:
                raise UserError(_('Please enter a Lot/SN.'))
            if float_compare(self.qty_done, 0, precision_rounding=rounding) < 0:
                raise UserError(_('Please enter a positive quantity.'))

            # Get the move lines associated with our component
            self.component_remaining_qty -= float_round(self.qty_done, precision_rounding=self.workorder_line_id.product_uom_id.rounding or rounding)
            self.workorder_line_id.write({
                'lot_id': self.lot_id.id,
                'qty_done': float_round(self.qty_done, precision_rounding=self.workorder_line_id.product_uom_id.rounding or rounding)
            })

            if continue_production:
                self._create_subsequent_checks()

        if self.test_type == 'picture' and not self.picture:
            raise UserError(_('Please upload a picture.'))

        if self.test_type not in ('measure', 'passfail'):
            self.current_quality_check_id.do_pass()

        if self.skip_completed_checks:
            self._change_quality_check(
                increment=1, children=1, checks=self.skipped_check_ids)
        else:
            self._change_quality_check(increment=1, children=1)



    def _create_or_update_finished_line(self):
        """
        1. Check that the final lot and the quantity producing is valid regarding
            other workorders of this production
        2. Save final lot and quantity producing to suggest on next workorder
        """
        self.ensure_one()

        final_lot_quantity = self.qty_production
        rounding = self.product_uom_id.rounding
        # Get the max quantity possible for current lot in other workorders
        for workorder in (self.production_id.workorder_ids - self):
            # We add the remaining quantity to the produced quantity for the
            # current lot. For 5 finished products: if in the first wo it
            # creates 4 lot A and 1 lot B and in the second it create 3 lot A
            # and it remains 2 units to product, it could produce 5 lot A.
            # In this case we select 4 since it would conflict with the first
            # workorder otherwise.
            line = workorder.finished_workorder_line_ids.filtered(
                lambda line: line.lot_id == self.finished_lot_id)
            line_without_lot = workorder.finished_workorder_line_ids.filtered(
                lambda line: line.product_id == workorder.product_id and not line.lot_id)
            quantity_remaining = workorder.qty_remaining + line_without_lot.qty_done
            quantity = line.qty_done + quantity_remaining

            if line and float_compare(quantity, final_lot_quantity, precision_rounding=rounding) <= 0:
                final_lot_quantity = quantity
            elif float_compare(quantity_remaining, final_lot_quantity, precision_rounding=rounding) < 0:
                final_lot_quantity = quantity_remaining

        # final lot line for this lot on this workorder.
        current_lot_lines = self.finished_workorder_line_ids.filtered(
            lambda line: line.lot_id == self.finished_lot_id)

        # removed to allow final_lot_quantity to exceed initial
        # this lot has already been produced
        # if float_compare(final_lot_quantity, current_lot_lines.qty_done + self.qty_producing, precision_rounding=rounding) < 0:
        #     raise UserError(_('You have produced %s %s of lot %s in the previous workorder. You are trying to produce %s in this one') %
        #         (final_lot_quantity, self.product_id.uom_id.name, self.finished_lot_id.name, current_lot_lines.qty_done + self.qty_producing))

        # Update workorder line that regiter final lot created
        if not current_lot_lines:
            current_lot_lines = self.env['mrp.workorder.line'].create({
                'finished_workorder_id': self.id,
                'product_id': self.product_id.id,
                'lot_id': self.finished_lot_id.id,
                'qty_done': self.qty_producing,
            })
        else:
            current_lot_lines.qty_done += self.qty_producing

    def record_production(self):
        if not self:
            return True

        self.ensure_one()
        self._check_company()

        if float_compare(self.qty_producing, 0, precision_rounding=self.product_uom_id.rounding) < 0:
            raise UserError(_('Please set the quantity you are currently producing. It should be different from zero.'))

        # If last work order, then post lots used
        if not self.next_work_order_id:
            self._update_finished_move()

        # Transfer quantities from temporary to final move line or make them final
        self._update_moves()

        # Transfer lot (if present) and quantity produced to a finished workorder line
        if self.product_tracking != 'none':
            self._create_or_update_finished_line()

        # Update workorder quantity produced
        self.qty_produced += self.qty_producing

        # Suggest a finished lot on the next workorder
        if self.next_work_order_id and self.product_tracking != 'none' and (not self.next_work_order_id.finished_lot_id or self.next_work_order_id.finished_lot_id == self.finished_lot_id):
            self.next_work_order_id._defaults_from_finished_workorder_line(self.finished_workorder_line_ids)
            # As we may have changed the quantity to produce on the next workorder,
            # make sure to update its wokorder lines
            self.next_work_order_id._apply_update_workorder_lines()

        # One a piece is produced, you can launch the next work order
        self._start_nextworkorder()

        # Test if the production is done
        rounding = self.production_id.product_uom_id.rounding
        if float_compare(self.qty_produced, self.production_id.product_qty, precision_rounding=rounding) < 0:
            previous_wo = self.env['mrp.workorder']
            if self.product_tracking != 'none':
                previous_wo = self.env['mrp.workorder'].search([
                    ('next_work_order_id', '=', self.id)
                ])
            candidate_found_in_previous_wo = False
            if previous_wo:
                candidate_found_in_previous_wo = self._defaults_from_finished_workorder_line(previous_wo.finished_workorder_line_ids)
            if not candidate_found_in_previous_wo:
                # self is the first workorder
                self.qty_producing = self.qty_remaining
                self.finished_lot_id = False
                if self.product_tracking == 'serial':
                    self.qty_producing = 1

            self._apply_update_workorder_lines()
        else:
            self.qty_producing = 0
            self.button_finish()
        return True

    @api.depends('qty_produced', 'qty_producing')
    def _compute_qty_remaining(self):
        """modify workorder product_qty if qty_remaining changes"""
        for wo in self:
            wo.qty_remaining = float_round(wo.qty_producing, precision_rounding=wo.production_id.product_uom_id.rounding)
            wo.production_id.product_qty = wo.qty_remaining

    def _compute_initial_qty(self):
        for wo in self:
            if wo.initial_component_remaining_qty and wo.initial_qty_remaining and self.env.context.get('tablet_view', False):
                pass
            else:
                wo.initial_component_remaining_qty = wo.component_remaining_qty
                wo.initial_qty_remaining = wo.qty_remaining

class MrpProductionWorkcenterLine(models.Model):
    _inherit = 'mrp.workorder'

    @api.onchange('qty_producing')
    def _onchange_qty_producing(self):
        if not self.env.context.get('tablet_view', False):
            if self.qty_producing <= 0:
                raise UserError(
                    _('You have to produce at least one %s.') % self.product_uom_id.name)
            line_values = self._update_workorder_lines()
            for values in line_values['to_create']:
                self.env[self._workorder_line_ids()._name].new(values)
            for line in line_values['to_delete']:
                if line in self.raw_workorder_line_ids:
                    self.raw_workorder_line_ids -= line
                else:
                    self.finished_workorder_line_ids -= line
            for line, vals in line_values['to_update'].items():
                line.update(vals)
