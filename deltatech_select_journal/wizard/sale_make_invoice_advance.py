# -*- coding: utf-8 -*-
# ©  2015-2018 Deltatech
#              Dorin Hongu <dhongu(@)gmail(.)com
# See README.rst file on addons root folder for license details



from odoo import api, fields, models, _





class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    @api.model
    def _default_journal(self):

        if self._context.get('default_journal_id', False):
            return self.env['account.journal'].browse(self._context.get('default_journal_id'))

        if not self._context.get('active_ids'):
            return False

        company_id = self._context.get('company_id', self.env.user.company_id.id)
        domain = [('type', '=', 'sale'), ('company_id', '=', company_id)]

        sale_obj = self.env['sale.order']
        order = sale_obj.browse(self._context.get('active_ids'))[0]
        if order and order.pricelist_id and order.pricelist_id.currency_id:
            if order.pricelist_id.currency_id != self.env.user.company_id.currency_id:
                domain += [('currency_id', '=', order.pricelist_id.currency_id.id)]

        return self.env['account.journal'].search(domain, limit=1)

    journal_id = fields.Many2one('account.journal', string='Journal',
                                 default=_default_journal,
                                 domain="[('type', '=', 'sale')]")

    @api.multi
    def create_invoices(self):
        new_self = self.with_context(default_journal_id=self.journal_id)
        return super(SaleAdvancePaymentInv, new_self).create_invoices()
