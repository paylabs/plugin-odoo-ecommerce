# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, _

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    paylabs_has_pending_tx = fields.Boolean(compute='_compute_paylabs_has_pending_tx')

    def _compute_paylabs_has_pending_tx(self):
        for order in self:
            txs = order.transaction_ids.filtered(lambda t: t.provider_code == 'paylabs' and t.state == 'pending')
            order.paylabs_has_pending_tx = bool(txs)

class AccountMove(models.Model):
    _inherit = 'account.move'

    paylabs_has_pending_tx = fields.Boolean(compute='_compute_paylabs_has_pending_tx')

    def _compute_paylabs_has_pending_tx(self):
        """ 
        Check if there is a pending Paylabs transaction for this invoice.
        """
        for move in self:
            txs = move.transaction_ids.filtered(lambda t: t.provider_code == 'paylabs' and t.state == 'pending')
            move.paylabs_has_pending_tx = bool(txs)
