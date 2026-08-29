from odoo import models, fields, api, _


class WahaMassComposer(models.TransientModel):
    """Mass / bulk WhatsApp sender opened from a list-view server action."""

    _name = 'waha.mass_composer'
    _description = 'WhatsApp Mass Sender'

    account_id = fields.Many2one(
        'waha.account', string='WAHA Account', required=True,
        domain="[('active','=',True)]",
    )
    template_id = fields.Many2one('waha.template', string='Template')
    body = fields.Text(string='Message', required=True)
    res_model = fields.Char(string='Source Model')
    res_ids = fields.Char(string='Source Record IDs (comma separated)')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get('account_id'):
            acc = self.env['waha.account'].search([('active', '=', True)], limit=1)
            if acc:
                res['account_id'] = acc.id
        return res

    @api.onchange('template_id')
    def _onchange_template(self):
        if self.template_id:
            self.body = self.template_id.body

    # ----------------------------------------------------------
    # Send
    # ----------------------------------------------------------
    def action_send(self):
        self.ensure_one()
        ids = [int(x) for x in (self.res_ids or '').split(',') if x.strip()]
        model = self.res_model
        if not model or not ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Nothing to send'),
                    'message': _('No records selected.'),
                    'type': 'warning',
                },
            }

        records = self.env[model].browse(ids)
        sent = 0
        failed = 0
        for rec in records:
            partner = (
                rec if model == 'res.partner'
                else (rec.partner_id if getattr(rec, 'partner_id', None) else None)
            )
            if not partner:
                failed += 1
                continue
            phone = partner.phone
            chat_id = self.account_id._to_chat_id(phone)
            if not chat_id:
                failed += 1
                continue
            text = self.template_id.render(rec) if self.template_id else self.body
            try:
                self.account_id.send_text(chat_id, text)
                self.env['waha.message'].create({
                    'account_id': self.account_id.id,
                    'partner_id': partner.id,
                    'phone': chat_id.split('@')[0],
                    'body': text,
                    'state': 'sent',
                    'model': model,
                    'res_id': rec.id,
                })
                sent += 1
            except Exception as e:
                self.env['waha.message'].create({
                    'account_id': self.account_id.id,
                    'partner_id': partner.id,
                    'phone': chat_id.split('@')[0],
                    'body': text,
                    'state': 'failed',
                    'error': str(e),
                    'model': model,
                    'res_id': rec.id,
                })
                failed += 1

        kind = 'success' if failed == 0 else 'warning'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mass WhatsApp Done'),
                'message': _('Sent: %s, Failed: %s') % (sent, failed),
                'type': kind,
            },
        }
