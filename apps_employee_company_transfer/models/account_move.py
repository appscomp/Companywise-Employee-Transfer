from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    company_transfer_id = fields.Many2one(
        'company.transfer', string="Company Transfer", copy=False, index='btree_not_null',
        ondelete='set null',
        help="Employee transfer this journal entry relates to.")
