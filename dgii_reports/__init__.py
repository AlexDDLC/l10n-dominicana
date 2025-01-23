# Part of Domincana Premium.
# See LICENSE file for full copyright and licensing details.
# © 2018 José López <jlopez@indexa.do>

from . import controllers
from . import models
from . import wizard

def update_taxes(env):
    tax_ids = env['ir.model.data'].search([
        ('model', '=', 'account.tax'),
        ('module', '=', 'l10n_do'),
    ])

    for tax_id in tax_ids:
        tax = env['account.tax'].browse(tax_id.res_id)

        tax.write({
            'l10n_do_tax_type': 'l10n_do_tax_type',
            'isr_retention_type': 'isr_retention_type',
            'tax_group_id': env.ref('account.tax_group_id').id
        })
