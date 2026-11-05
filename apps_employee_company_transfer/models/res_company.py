from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    journal_id = fields.Many2one(
        'account.journal', string="Salary Journal",
        help="Default journal proposed for the salary of employees transferred to this company.")
    gratuity_debit_account_id = fields.Many2one(
        'account.account', string="Gratuity Debit Account")
    gratuity_credit_account_id = fields.Many2one(
        'account.account', string="Gratuity Credit Account")
