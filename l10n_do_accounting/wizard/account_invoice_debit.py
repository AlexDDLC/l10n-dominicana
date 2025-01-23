import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

try:
    from stdnum.do import ncf as ncf_validation
except (ImportError, IOError) as err:
    _logger.debug(err)


class AccountMoveDebit(models.TransientModel):
    _inherit = "account.debit.note"

    @api.model
    def default_get(self, fields):
        res = super(AccountMoveDebit, self).default_get(fields)
        context = dict(self._context or {})
        invoice_ids = self.env["account.move"].browse(context.get("active_ids"))
        res.update({
            'is_fiscal_debit': set(invoice_ids.mapped("is_l10n_do_fiscal_invoice")) == {True},
            'is_vendor_debit': set(invoice_ids.mapped("move_type")) == {'in_invoice'}
        })

        return res

    @api.model
    def _get_debit_method_selection(self):
        if self._context.get("debit_note", False):
            return [
                ('refund', 'Partial Debit note'),
                ('cancel', 'Full Debit note'),
            ]
        return [
            ('refund', 'Partial Refund'),
            ('cancel', 'Full Refund'),
            ('modify', 'Full refund and new draft invoice')
        ]

    debit_method = fields.Selection(
        selection=_get_debit_method_selection,
        default="refund",
        string='Debit Method',
        required=True,
        help='Choose how you want to debit this invoice. You cannot "modify" nor "cancel" if the invoice is already reconciled.'
    )

    is_vendor_debit = fields.Boolean(
        string='Vendor refund',
    )

    debit_ref = fields.Char(
        string='NCF'
    )

    ncf_expiration_date = fields.Date(
        string="Valid until",
    )

    is_fiscal_debit = fields.Boolean(
        string='Fiscal refund'
    )


    def reverse_moves(self, is_modify=False):
        self.ensure_one()

        if self.refund_ref and self.is_fiscal_refund:
            self.env['account.fiscal.type'].check_format_fiscal_number(
                self.refund_ref,
                'in_refund'
            )
        return super(AccountMoveDebit, self).reverse_moves(is_modify=is_modify)

    def _prepare_default_debit(self, move):
        res = super(AccountMoveDebit, self)._prepare_default_debit(move)

        if self.is_fiscal_refund:
            res.update({
                'ref': self.debit_ref,
                'origin_out': move.ref,
                'expense_type': move.expense_type,
                'income_type': move.income_type,
                'ncf_expiration_date': self.ncf_expiration_date,
                'fiscal_type_id': False
            })

        return res
