from odoo import models, fields


class WahaMessage(models.Model):
    """Log of every WhatsApp message sent through this module."""

    _name = 'waha.message'
    _description = 'WhatsApp Message Log'
    _order = 'create_date desc'

    account_id = fields.Many2one('waha.account', string='WAHA Account')
    partner_id = fields.Many2one('res.partner', string='Recipient')
    phone = fields.Char(string='Phone (chat id digits)')
    body = fields.Text(string='Message')
    state = fields.Selection(
        [('sent', 'Sent'), ('failed', 'Failed')], string='State', default='sent',
    )
    error = fields.Text(string='Error')
    model = fields.Char(string='Source Model')
    res_id = fields.Integer(string='Source Record ID')
    create_date = fields.Datetime(string='Sent On', readonly=True)
