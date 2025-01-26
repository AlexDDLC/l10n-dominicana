import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

try:
    from stdnum.do import ncf as ncf_validation
except (ImportError, IOError) as err:
    _logger.debug(err)


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"


    @api.model
    def default_get(self, fields):
        res = super(AccountMoveReversal, self).default_get(fields)
        context = dict(self._context or {})
        invoice_ids = self.env["account.move"].browse(context.get("active_ids"))
        res.update({
            'is_fiscal_refund': set(invoice_ids.mapped("is_l10n_do_fiscal_invoice")) == {True},
            'is_vendor_refund': set(invoice_ids.mapped("move_type")) == {'in_invoice'}
        })

        return res

    @api.model
    def _get_refund_method_selection(self):
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

    refund_method = fields.Selection(
        selection=_get_refund_method_selection,
        default="refund",
        string='Credit Method',
        required=True,
        help='Choose how you want to credit this invoice. You cannot "modify" nor "cancel" if the invoice is already reconciled.'
    )

    is_vendor_refund = fields.Boolean(
        string='Vendor refund',
    )

    refund_ref = fields.Char(
        string='NCF'
    )

    ncf_expiration_date = fields.Date(
        string="Valid until",
    )

    is_fiscal_refund = fields.Boolean(
        string='Fiscal refund'
    )


    def compute_refund(self, mode="refund"):
        xml_id = False
        created_inv = []
        for wizard in self:
            inv_obj = self.env["account.move"]
            context = dict(self._context or {})
            for inv in inv_obj.browse(context.get("active_ids")):
                if inv.state in ["draft", "cancel"]:
                    raise UserError(
                        _(
                            "Cannot create credit note for the draft/cancelled "
                            "invoice."
                        )
                    )
                if inv.reconciled and mode in ("cancel", "modify"):
                    raise UserError(
                        _(
                            "Cannot create a credit note for the invoice which is "
                            "already reconciled, invoice should be unreconciled "
                            "first, then only you can add credit note for "
                            "this invoice."
                        )
                    )

                action_map = {
                    "out_invoice": "action_invoice_out_refund",
                    "out_refund": "action_invoice_tree1",
                    "in_invoice": "action_invoice_in_refund",
                    "in_refund": "action_invoice_tree2",
                }
                xml_id = action_map[inv.move_type]
        if xml_id:
            result = self.env.ref("account.%s" % xml_id).read()[0]
            invoice_domain = safe_eval(result["domain"])
            invoice_domain.append(("id", "in", created_inv))
            result["domain"] = invoice_domain
            return result
        return True


    def reverse_moves(self, is_modify=False):
        self.ensure_one()
        if self.refund_ref and self.is_fiscal_refund:
            self.env['account.fiscal.type'].check_format_fiscal_number(
                self.refund_ref,
                'in_refund'
            )
        return super(AccountMoveReversal, self).reverse_moves(is_modify=is_modify)


    def _prepare_default_reversal(self, move):
        res = super(AccountMoveReversal, self)._prepare_default_reversal(move)

        if self.is_fiscal_refund:
            res.update({
                'ref': self.refund_ref,
                'origin_out': move.ref,
                'expense_type': move.expense_type,
                'income_type': move.income_type,
                'ncf_expiration_date': self.ncf_expiration_date,
                'fiscal_type_id': False
            })

        return res
