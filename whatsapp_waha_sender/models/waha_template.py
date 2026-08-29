import re

from odoo import models, fields, api, _


class WahaTemplate(models.Model):
    """Reusable WhatsApp message template with {{variable}} substitution."""

    _name = 'waha.template'
    _description = 'WhatsApp Message Template'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    body = fields.Text(
        string='Message Body', required=True,
        help=(
            'You can use {{field}} variables resolved against the source '
            'document, e.g. {{partner_id.name}}, {{name}}, {{amount_total}}, '
            '{{invoice_date}}. Use {{partner.xxx}} to reach partner fields.'
        ),
    )
    active = fields.Boolean(default=True)

    # ----------------------------------------------------------
    # Rendering
    # ----------------------------------------------------------
    def render(self, record):
        self.ensure_one()
        if not record:
            return self.body or ''

        def repl(match):
            path = match.group(1).strip()
            try:
                val = self._resolve(record, path)
                if val is False or val is None:
                    return ''
                return str(val)
            except Exception:
                return ''

        return re.sub(r'\{\{\s*([^}]+?)\s*\}\}', repl, self.body or '')

    def _resolve(self, record, path):
        obj = record
        parts = path.split('.')
        # Convenience alias: "partner" / "customer" -> record.partner_id
        if parts[0] in ('partner', 'customer') and hasattr(record, 'partner_id'):
            obj = record.partner_id
            parts = parts[1:]
        for part in parts:
            if obj is False or obj is None:
                return ''
            attr = getattr(obj, part, None)
            if callable(attr):
                attr = attr()
            obj = attr
        return obj
