from odoo import models, fields, api


def _open_whatsapp_composer(self):
    """Open the single-record WhatsApp composer for the current document."""
    self.ensure_one()
    if self._name == 'res.partner':
        partner = self
    else:
        partner = self.partner_id if getattr(self, 'partner_id', None) else self.env['res.partner']
    ctx = {
        'default_model': self._name,
        'default_res_id': self.id,
        'default_partner_id': partner.id if partner else False,
        'default_attach_invoice_pdf': (self._name == 'account.move'),
    }
    return {
        'type': 'ir.actions.act_window',
        'name': 'Send WhatsApp',
        'res_model': 'waha.composer',
        'view_mode': 'form',
        'target': 'new',
        'context': ctx,
    }


class CrmLeadWA(models.Model):
    _inherit = 'crm.lead'

    waha_chat_url = fields.Char(compute='_compute_waha_chat_url')

    def _compute_waha_chat_url(self):
        for r in self:
            r.waha_chat_url = '/waha/chat/partner/%s' % r.partner_id.id if r.partner_id else ''

    def action_send_whatsapp(self):
        return _open_whatsapp_composer(self)


class SaleOrderWA(models.Model):
    _inherit = 'sale.order'

    waha_chat_url = fields.Char(compute='_compute_waha_chat_url')

    def _compute_waha_chat_url(self):
        for r in self:
            r.waha_chat_url = '/waha/chat/partner/%s' % r.partner_id.id if r.partner_id else ''

    def action_send_whatsapp(self):
        return _open_whatsapp_composer(self)


class AccountMoveWA(models.Model):
    _inherit = 'account.move'

    waha_chat_url = fields.Char(compute='_compute_waha_chat_url')

    def _compute_waha_chat_url(self):
        for r in self:
            r.waha_chat_url = '/waha/chat/partner/%s' % r.partner_id.id if r.partner_id else ''

    def action_send_whatsapp(self):
        return _open_whatsapp_composer(self)


class ResPartnerWA(models.Model):
    _inherit = 'res.partner'

    waha_chat_html = fields.Html(compute='_compute_waha_chat_html', sanitize=False)

    def _compute_waha_chat_html(self):
        for r in self:
            url = '/waha/chat/partner/%s' % r.id
            r.waha_chat_html = (
                '<div style="margin-bottom:8px;">'
                '<a href="%s" target="_blank" '
                'style="display:inline-block;padding:4px 12px;background:#25d366;'
                'color:#fff;border-radius:6px;text-decoration:none;font-size:13px;">'
                'Open in new window</a> '
                '<span style="color:#6b7280;font-size:12px;">'
                'Read-only WhatsApp history (synced from WAHA).</span>'
                '</div>'
                '<iframe src="%s" '
                'style="width:100%%;height:620px;border:1px solid #ccc;border-radius:6px;">'
                '</iframe>'
            ) % (url, url)

    def action_send_whatsapp(self):
        return _open_whatsapp_composer(self)
