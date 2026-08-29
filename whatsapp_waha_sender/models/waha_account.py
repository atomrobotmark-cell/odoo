import logging
import re

import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WahaAccount(models.Model):
    """WAHA connection configuration.

    WAHA (https://github.com/devlikeapro/waha) exposes a REST API.
    This model stores the endpoint and credentials and provides the
    low-level send helpers used by the composer and mass sender.
    """

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
        """Convert a phone number to a WAHA chat id (individual).

        WAHA uses ``<digits>@c.us`` for single contacts, where digits is the
        international number without the leading ``+`` (e.g. 8615510979062).
        """
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
                # Odoo container inherits HTTP_PROXY from the docker daemon; force
                # a direct connection to WAHA (same host, published port).
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
    def _get(self, endpoint, params=None):
        self.ensure_one()
        # WAHA REST layout:
        #   - session mgmt : /api/sessions/...        (plural, e.g. start, list)
        #   - chat/message : /api/{session}/chats/...  (singular 'api', session
        #                    is a path param, NOT under /api/sessions/)
        # e.g. GET /api/default/chats  and  /api/default/chats/{id}/messages
        url = f'{self.base_url.rstrip("/")}/api/{self.session or "default"}/{endpoint}'
        try:
            resp = requests.get(
                url, params=params or {}, headers=self._get_headers(), timeout=30,
                # See _post: bypass the daemon-injected HTTP_PROXY so Odoo talks
                # to WAHA directly.
                proxies={'http': None, 'https': None},
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('WAHA GET %s failed: %s', url, e)
            raise UserError(_('WAHA request failed: %s') % e)

    def get_messages(self, chat_id, limit=50, offset=0):
        """Return raw WAHA message objects for a chat id."""
        self.ensure_one()
        if not chat_id:
            return []
        data = self._get(f'chats/{chat_id}/messages',
                         {'limit': limit, 'offset': offset})
        # WAHA returns either a list or a dict with a "messages" key
        if isinstance(data, dict):
            return data.get('messages', [])
        return data or []

    @api.model
    def _wa_number(self, partner):
        """Best-effort WhatsApp number for a partner (Odoo 19: phone)."""
        phone = partner.phone or ''
        return phone

    def sync_partner_messages(self, partner, limit=100):
        """Pull a partner's WhatsApp chat into the cache and return count."""
        self.ensure_one()
        chat_id = self._to_chat_id(self._wa_number(partner))
        if not chat_id:
            return 0
        messages = self.get_messages(chat_id, limit=limit)
        return self.env['waha.chat.message'].upsert_from_waha(
            self, partner, chat_id, messages)

    def sync_company_messages(self, company, limit=100):
        """Sync chat history for a company and all of its contacts."""
        self.ensure_one()
        count = 0
        partners = company | company.child_ids.filtered(lambda p: p.phone)
        for partner in partners:
            count += self.sync_partner_messages(partner, limit=limit)
        return count

    def sync_chat_tree(self, partner, limit=100):
        """Sync chat for a partner, or the whole contact tree if a company."""
        self.ensure_one()
        if partner.is_company:
            return self.sync_company_messages(partner, limit=limit)
        return self.sync_partner_messages(partner, limit=limit)

    @api.model
    def _norm_digits(self, value):
        return re.sub(r'\D', '', value or '')

    def _find_partner_for_chat(self, chat_id):
        """Find a res.partner whose number matches the chat id (suffix match).

        WAHA chat ids look like ``8615510979062@c.us``. We match on the
        longest numeric suffix so that differing country-code prefixes still
        resolve, as long as each partner stores at least 8 digits.
        """
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
        chats = self._get('chats') or []
        if isinstance(chats, dict):
            chats = chats.get('chats', [])
        total = 0
        for chat in chats:
            chat_id = chat.get('id')
            if not chat_id:
                continue
            partner = self._find_partner_for_chat(chat_id)
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
        # Try /api/version first, then fall back to listing sessions
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
