# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo.tools import float_compare, float_round
from odoo import models, fields, api, _


class MrpAbstractWorkorder(models.AbstractModel):
    _inherit = "mrp.abstract.workorder"

    @api.onchange('qty_producing')
    def _onchange_qty_producing(self):
        """ Modify the qty currently producing will modify the existing
        workorder line in order to match the new quantity to consume for each
        component and their reserved quantity.
        """
        if not self.env.context.get('tablet_view', False):
            if self.qty_producing <= 0:
                raise UserError(_('You have to produce at least one %s.') % self.product_uom_id.name)
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

    def _update_workorder_lines(self):
        """ Update workorder lines, according to the new qty currently
        produced. It returns a dict with line to create, update or delete.
        It do not directly write or unlink the line because this function is
        used in onchange and request that write on db (e.g. workorder creation).
        sets untracked component qty_done here 
        """
        line_values = {'to_create': [], 'to_delete': [], 'to_update': {}}
        if not self.env.context.get('tablet_view', False):
            # moves are actual records
            move_finished_ids = self.move_finished_ids._origin.filtered(
                lambda move: move.product_id != self.product_id and move.state not in ('done', 'cancel'))
            move_raw_ids = self.move_raw_ids._origin.filtered(
                lambda move: move.state not in ('done', 'cancel'))
            for move in move_raw_ids | move_finished_ids:
                move_workorder_lines = self._workorder_line_ids().filtered(
                    lambda w: w.move_id == move)

                # Compute the new quantity for the current component
                rounding = move.product_uom.rounding
                new_qty = self._prepare_component_quantity(move, self.qty_producing)

                # In case the production uom is different than the workorder uom
                # it means the product is serial and production uom is not the reference
                new_qty = self.product_uom_id._compute_quantity(
                    new_qty,
                    self.production_id.product_uom_id,
                    round=False
                )
                qty_todo = float_round(
                    new_qty - sum(move_workorder_lines.mapped('qty_to_consume')), precision_rounding=rounding)

                # Remove or lower quantity on exisiting workorder lines
                if float_compare(qty_todo, 0.0, precision_rounding=rounding) < 0:
                    qty_todo = abs(qty_todo)
                    # Try to decrease or remove lines that are not reserved and
                    # partialy reserved first. A different decrease strategy could
                    # be define in _unreserve_order method.
                    for workorder_line in move_workorder_lines.sorted(key=lambda wl: wl._unreserve_order()):
                        if float_compare(qty_todo, 0, precision_rounding=rounding) <= 0:
                            break
                        # If the quantity to consume on the line is lower than the
                        # quantity to remove, the line could be remove.
                        if float_compare(workorder_line.qty_to_consume, qty_todo, precision_rounding=rounding) <= 0:
                            qty_todo = float_round(
                                qty_todo - workorder_line.qty_to_consume, precision_rounding=rounding)
                            if line_values['to_delete']:
                                line_values['to_delete'] |= workorder_line
                            else:
                                line_values['to_delete'] = workorder_line
                        # decrease the quantity on the line
                        else:
                            new_val = workorder_line.qty_to_consume - qty_todo
                            # avoid to write a negative reserved quantity
                            new_reserved = max(
                                0, workorder_line.qty_reserved - qty_todo)
                            line_values['to_update'][workorder_line] = {
                                'qty_to_consume': new_val,
                                'qty_done': new_val,
                                'qty_reserved': new_reserved,
                            }
                            qty_todo = 0
                else:
                    # Search among wo lines which one could be updated
                    qty_reserved_wl = defaultdict(float)
                    # Try to update the line with the greater reservation first in
                    # order to promote bigger batch.
                    for workorder_line in move_workorder_lines.sorted(key=lambda wl: wl.qty_reserved, reverse=True):
                        rounding = workorder_line.product_uom_id.rounding
                        if float_compare(qty_todo, 0, precision_rounding=rounding) <= 0:
                            break
                        move_lines = workorder_line._get_move_lines()
                        qty_reserved_wl[workorder_line.lot_id] += workorder_line.qty_reserved
                        # The reserved quantity according to exisiting move line
                        # already produced (with qty_done set) and other production
                        # lines with the same lot that are currently on production.
                        qty_reserved_remaining = sum(move_lines.mapped('product_uom_qty')) - sum(
                            move_lines.mapped('qty_done')) - qty_reserved_wl[workorder_line.lot_id]
                        if float_compare(qty_reserved_remaining, 0, precision_rounding=rounding) > 0:
                            qty_to_add = min(qty_reserved_remaining, qty_todo)
                            line_values['to_update'][workorder_line] = {
                                'qty_done': workorder_line.qty_to_consume + qty_to_add,
                                'qty_to_consume': workorder_line.qty_to_consume + qty_to_add,
                                'qty_reserved': workorder_line.qty_reserved + qty_to_add,
                            }
                            qty_todo -= qty_to_add
                            qty_reserved_wl[workorder_line.lot_id] += qty_to_add

                        # If a line exists without reservation and without lot. It
                        # means that previous operations could not find any reserved
                        # quantity and created a line without lot prefilled. In this
                        # case, the system will not find an existing move line with
                        # available reservation anymore and will increase this line
                        # instead of creating a new line without lot and reserved
                        # quantities.
                        if not workorder_line.qty_reserved and not workorder_line.lot_id and workorder_line.product_tracking != 'serial':
                            line_values['to_update'][workorder_line] = {
                                'qty_done': workorder_line.qty_to_consume + qty_todo,
                                'qty_to_consume': workorder_line.qty_to_consume + qty_todo,
                            }
                            qty_todo = 0

                    # if there are still qty_todo, create new wo lines
                    if float_compare(qty_todo, 0.0, precision_rounding=rounding) > 0:
                        for values in self._generate_lines_values(move, qty_todo):
                            line_values['to_create'].append(values)
        return line_values
