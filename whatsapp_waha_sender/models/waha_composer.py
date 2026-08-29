import base64
import re

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WahaComposer(models.TransientModel):
    """Single-record WhatsApp composer opened from CRM/SO/Invoice forms."""

    _name = 'waha.composer'
    _description = 'WhatsApp Composer'

    account_id = fields.Many2one(
        'waha.account', string='WAHA Account', required=True,
        domain="[('active','=',True)]",
    )
    partner_id = fields.Many2one('res.partner', string='Recipient')
    phone = fields.Char(
        string='Phone (international digits, no +)',
        help='e.g. 8615510979062. Auto-filled from the recipient.',
    )
    template_id = fields.Many2one('waha.template', string='Template')
    body = fields.Text(string='Message', required=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'waha_composer_attachment_rel',
        'composer_id', 'attachment_id', string='Attachments',
    )
    model = fields.Char(string='Source Model')
    res_id = fields.Integer(string='Source Record ID')
    attach_invoice_pdf = fields.Boolean(
        string='Attach invoice PDF',
        help='Only available when sending from an invoice (account.move).',
    )

    # ----------------------------------------------------------
    # Defaults / onchange
    # ----------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get('account_id'):
            acc = self.env['waha.account'].search([('active', '=', True)], limit=1)
            if acc:
                res['account_id'] = acc.id
        return res

    @api.onchange('partner_id')
    def _onchange_partner(self):
        if self.partner_id:
            phone = self.partner_id.phone
            if phone:
                self.phone = re.sub(r'\D', '', phone)

    @api.onchange('template_id')
    def _onchange_template(self):
        if not self.template_id:
            return
        if self.model and self.res_id:
            rec = self.env[self.model].browse(self.res_id)
            if rec.exists():
                self.body = self.template_id.render(rec)
                return
        self.body = self.template_id.body

    # ----------------------------------------------------------
    # Send
    # ----------------------------------------------------------
    def _resolve_phone(self):
        phone = self.phone or (self.partner_id.phone)
        chat_id = self.account_id._to_chat_id(phone)
        if not chat_id:
            raise UserError(_('No valid phone number for the recipient.'))
        return chat_id

    def action_send(self):
        self.ensure_one()
        chat_id = self._resolve_phone()
        account = self.account_id
        attachments = self.attachment_ids

        if self.attach_invoice_pdf and self.model == 'account.move':
            move = self.env['account.move'].browse(self.res_id)
            if move.exists():
                pdf = self.env.ref('account.account_invoices')._render_qweb_pdf(
                    [move.id]
                )[0]
                att = self.env['ir.attachment'].create({
                    'name': (move.name or 'invoice') + '.pdf',
                    'datas': base64.b64encode(pdf),
                    'mimetype': 'application/pdf',
                    'res_model': 'waha.composer',
                    'res_id': self.id,
                })
                attachments |= att

        try:
            if attachments:
                for att in attachments:
                    account.send_file(
                        chat_id, att.datas, att.name,
                        caption=self.body or '', mimetype=att.mimetype or 'application/pdf',
                    )
            else:
                account.send_text(chat_id, self.body or '')
        except UserError:
            self._log(chat_id, self.body, 'failed')
            raise

        self._log(chat_id, self.body, 'sent')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('WhatsApp Sent'),
                'message': _('Message sent to %s') % chat_id,
                'type': 'success',
            },
        }

    def _log(self, chat_id, body, state, error=None):
        self.env['waha.message'].create({
            'account_id': self.account_id.id,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'phone': chat_id.split('@')[0],
            'body': body,
            'state': state,
            'error': error,
            'model': self.model,
            'res_id': self.res_id,
        })
