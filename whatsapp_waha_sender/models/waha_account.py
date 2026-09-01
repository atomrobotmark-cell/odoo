import logging
import re

import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WahaAccount(models.Model):
    """WAHA connection configuration."""

    _name = 'waha.account'
    _description = 'WAHA WhatsApp Account'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    base_url = fields.Char(
        string='WAHA Base URL', required=True,
        help='WAHA API base URL, e.g. http://localhost:3000',
    )
    api_key = fields.Char(
        string='API Key',
        help='WAHA API key sent as the X-Api-Key header. Leave empty if not configured.',
    )
    session = fields.Char(
        string='Session', default='default', required=True,
        help='WAHA session name (the one you started / scanned QR for).',
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    def _get_headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['X-Api-Key'] = self.api_key
        return headers

    @api.model
    def _to_chat_id(self, phone):
        """Convert a phone number to a WAHA chat id (individual)."""
        digits = re.sub(r'\D', '', phone or '')
        if not digits:
            return False
        return f'{digits}@c.us'

    def _post(self, endpoint, payload):
        self.ensure_one()
        url = f'{self.base_url.rstrip("/")}/api/{endpoint}'
        try:
            resp = requests.post(
                url, json=payload, headers=self._get_headers(), timeout=30,
                proxies={'http': None, 'https': None},
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('WAHA request to %s failed: %s', url, e)
            raise UserError(_('WAHA request failed: %s') % e)

    def send_text(self, chat_id, text):
        return self._post('sendText', {
            'session': self.session or 'default',
            'chatId': chat_id,
            'text': text,
        })

    def send_file(self, chat_id, base64_data, filename, caption='',
                  mimetype='application/pdf'):
        payload = {
            'session': self.session or 'default',
            'chatId': chat_id,
            'file': {
                'base64': base64_data,
                'mimetype': mimetype,
                'fileName': filename,
            },
            'caption': caption or '',
        }
        return self._post('sendFile', payload)

    # ----------------------------------------------------------
    # Read helpers (chat history viewer)
    # ----------------------------------------------------------
    def _get(self, endpoint, params=None, timeout=60):
        self.ensure_one()
        url = f'{self.base_url.rstrip("/")}/api/{self.session or "default"}/{endpoint}'
        try:
            resp = requests.get(
                url, params=params or {}, headers=self._get_headers(), timeout=timeout,
                proxies={'http': None, 'https': None},
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('WAHA GET %s failed: %s', url, e)
            raise UserError(_('WAHA request failed: %s') % e)

    def get_messages(self, chat_id, limit=50, offset=0):
        """Return raw WAHA message objects for a chat id.

        Uses adaptive timeout: starts with 60s, falls back to smaller
        batches if the server is slow.
        """
        self.ensure_one()
        if not chat_id:
            return []

        # WAHA performance: limit<=10 is fast (0.1s), limit>=15 is slow (12s+)
        # Use smaller default to avoid timeouts, especially for media-heavy chats
        actual_limit = min(limit, 30)
        try:
            data = self._get(f'chats/{chat_id}/messages',
                             {'limit': actual_limit, 'offset': offset}, timeout=60)
            if isinstance(data, dict):
                return data.get('messages', [])
            return data or []
        except UserError:
            # If timed out, retry with minimal limit
            if actual_limit > 10:
                _logger.warning('WAHA timeout for %s with limit=%d, retrying with limit=10',
                                chat_id, actual_limit)
                try:
                    data = self._get(f'chats/{chat_id}/messages',
                                     {'limit': 10, 'offset': offset}, timeout=15)
                    if isinstance(data, dict):
                        return data.get('messages', [])
                    return data or []
                except UserError:
                    pass
            return []

    @api.model
    def _wa_number(self, partner):
        """Best-effort WhatsApp number for a partner."""
        phone = partner.phone or ''
        first = re.split(r'[;,]', phone)[0].strip()
        return first

    def _norm(self, s):
        """Normalize string for fuzzy matching."""
        return re.sub(r'[^a-z0-9]', '', (s or '').lower())

    def _find_chat_id_for_partner(self, partner):
        """Find the correct WAHA chat_id for a partner.

        WAHA now uses @lid format (e.g. 130000204361798@lid) instead of
        @c.us. We search the WAHA chat list to find the correct chat_id
        by matching the partner's name or phone number.
        """
        self.ensure_one()

        # First try @c.us format (old format, might still work)
        phone = self._wa_number(partner)
        chat_id_cus = self._to_chat_id(phone)

        # Get WAHA chat list
        try:
            chats = self._get('chats', {'limit': 600})
        except Exception:
            chats = []
        if isinstance(chats, dict):
            chats = chats.get('chats', [])

        # Normalize partner info for matching
        partner_name = self._norm(partner.name or '')
        partner_phone = re.sub(r'\D', '', phone or '')

        for ch in chats:
            cid = ch.get('id', '')
            if isinstance(cid, dict):
                cid = cid.get('_serialized', '')
            if '@g.us' in cid or '@broadcast' in cid:
                continue
            ch_name = self._norm(ch.get('name', ''))

            # Match by name (fuzzy: one contains the other)
            if partner_name and ch_name and len(partner_name) >= 3 and len(ch_name) >= 3:
                if partner_name in ch_name or ch_name in partner_name:
                    return cid

            # Match by phone digits in chat_id
            if partner_phone and len(partner_phone) >= 8:
                cid_digits = re.sub(r'\D', '', cid.split('@')[0])
                if cid_digits and len(cid_digits) >= 8:
                    if cid_digits.endswith(partner_phone[-10:]) or partner_phone.endswith(cid_digits[-10:]):
                        return cid

        # Fallback: return @c.us format
        return chat_id_cus

    def sync_partner_messages(self, partner, limit=50):
        """Pull a partner's WhatsApp chat into the cache and return count."""
        self.ensure_one()
        if isinstance(partner, (int, list)):
            partner = self.env['res.partner'].browse(partner if isinstance(partner, list) else [partner])

        chat_id = self._find_chat_id_for_partner(partner)
        if not chat_id:
            return 0

        messages = self.get_messages(chat_id, limit=limit)
        return self.env['waha.chat.message'].upsert_from_waha(
            self, partner, chat_id, messages)

    def sync_company_messages(self, company, limit=50):
        """Sync chat history for a company and all of its contacts."""
        self.ensure_one()
        if isinstance(company, (int, list)):
            company = self.env['res.partner'].browse(company if isinstance(company, list) else [company])
        count = 0
        partners = company | company.child_ids.filtered(lambda p: p.phone)
        for partner in partners:
            count += self.sync_partner_messages(partner, limit=limit)
        return count

    def sync_chat_tree(self, partner, limit=50):
        """Sync chat for a partner, or the whole contact tree if a company."""
        self.ensure_one()
        if isinstance(partner, (int, list)):
            partner = self.env['res.partner'].browse(partner if isinstance(partner, list) else [partner])
        if isinstance(partner, (int, list)):
            partner = self.env["res.partner"].browse(partner if isinstance(partner, list) else [partner])
        if partner.is_company:
            return self.sync_company_messages(partner, limit=limit)
        return self.sync_partner_messages(partner, limit=limit)

    @api.model
    def _norm_digits(self, value):
        return re.sub(r'\D', '', value or '')

    def _find_partner_for_chat(self, chat_id):
        """Find a res.partner whose number matches the chat id."""
        self.ensure_one()
        digits = self._norm_digits(chat_id.split('@')[0])
        if not digits:
            return self.env['res.partner']
        partners = self.env['res.partner'].search([
            ('phone', '!=', False),
        ])
        for partner in partners:
            for num in (partner.phone,):
                d = self._norm_digits(num)
                if len(d) >= 8 and (digits.endswith(d) or d.endswith(digits)):
                    return partner
        return self.env['res.partner']

    def sync_all_partners(self, limit_per_chat=50):
        """Pull every WAHA chat and store messages under matching partners."""
        self.ensure_one()
        chats = self._get('chats', {'limit': 600}) or []
        if isinstance(chats, dict):
            chats = chats.get('chats', [])
        total = 0
        for chat in chats:
            chat_id = chat.get('id')
            if isinstance(chat_id, dict):
                chat_id = chat_id.get('_serialized', '')
            if not chat_id:
                continue
            if '@g.us' in chat_id or '@broadcast' in chat_id:
                continue
            partner = self._find_partner_for_chat(chat_id)
            if not partner:
                # Try name matching
                ch_name = chat.get('name', '')
                if ch_name:
                    norm_name = self._norm(ch_name)
                    all_partners = self.env['res.partner'].search([])
                    for p in all_partners:
                        if p.name and self._norm(p.name) == norm_name:
                            partner = p
                            break
            if not partner:
                continue
            messages = self.get_messages(chat_id, limit=limit_per_chat)
            total += self.env['waha.chat.message'].upsert_from_waha(
                self, partner, chat_id, messages)
        return total

    def action_sync_all(self):
        self.ensure_one()
        try:
            count = self.sync_all_partners()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WhatsApp Sync Done'),
                    'message': _('Pulled %s messages.') % count,
                    'type': 'success',
                },
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('WhatsApp Sync Failed'),
                    'message': str(e),
                    'type': 'danger',
                },
            }

    def action_test_connection(self):
        self.ensure_one()
        for url in (
            f'{self.base_url.rstrip("/")}/api/version',
            f'{self.base_url.rstrip("/")}/api/sessions',
        ):
            try:
                resp = requests.get(
                    url, headers=self._get_headers(), timeout=10,
                    proxies={'http': None, 'https': None},
                )
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                version = (data.get('version') or data.get('waha')
                           or ('%d sessions' % len(data) if isinstance(data, list) else 'OK'))
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('WAHA Connected'),
                        'message': _('WAHA version: %s') % version,
                        'type': 'success',
                    },
                }
            except Exception:
                continue
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('WAHA Connection Failed'),
                'message': _('Cannot reach %s') % self.base_url,
                'type': 'danger',
            },
        }
