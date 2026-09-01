import datetime
import logging

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class WahaChatMessage(models.Model):
    """Cached WhatsApp chat history pulled from WAHA (read-only viewer).

    Records are upserted from WAHA's message history so the chat can be
    displayed inside Odoo even when the WAHA session is offline, and so it
    is searchable / auditable.
    """

    _name = 'waha.chat.message'
    _description = 'WAHA Chat Message (cached)'
    _order = 'msg_timestamp desc'
    _rec_name = 'body'

    account_id = fields.Many2one('waha.account', string='WAHA Account', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='cascade')
    chat_id = fields.Char(string='WAHA Chat ID', help='e.g. 8615510979062@c.us')
    wa_msg_id = fields.Char(string='WAHA Message ID', index=True)
    direction = fields.Selection([
        ('in', 'Received'),
        ('out', 'Sent'),
    ], string='Direction')
    sender_name = fields.Char(string='Sender')
    body = fields.Text(string='Message')
    media_type = fields.Char(string='Media Type')
    media_url = fields.Char(string='Media URL')
    msg_timestamp = fields.Datetime(string='WhatsApp Time')
    attachment_id = fields.Many2one("ir.attachment", string="Media Attachment", ondelete="set null")
    fetched_at = fields.Datetime(string='Fetched At', default=fields.Datetime.now)


    @api.model
    def upsert_from_waha(self, account, partner, chat_id, messages):
        """Upsert a list of WAHA message dicts into the cache.

        ``messages`` items are expected to be WAHA message objects with at
        least ``id``, ``fromMe``, ``body`` and ``timestamp``.
        """
        for msg in messages or []:
            wa_id = msg.get('id')
            if not wa_id:
                continue
            ts = msg.get('timestamp')
            msg_dt = fields.Datetime.to_string(
                datetime.datetime.fromtimestamp(ts)) if ts else False
            # Extract media URL and type from WAHA response
            media = msg.get('media') or {}
            media_url = media.get('url') or ''
            media_mimetype = media.get('mimetype') or ''
            # Infer media_type from mimetype (WAHA puts it in media.mimetype, not top-level type)
            media_type = ''
            if media_mimetype:
                if 'image' in media_mimetype:
                    media_type = 'image'
                elif 'video' in media_mimetype:
                    media_type = 'video'
                elif 'audio' in media_mimetype or 'ogg' in media_mimetype:
                    media_type = 'audio'
                elif 'pdf' in media_mimetype:
                    media_type = 'document'
                else:
                    media_type = media_mimetype.split('/')[-1]
            elif msg.get('type'):
                media_type = msg.get('type')
            # Fix localhost URLs to use the WAHA server address
            if media_url and 'localhost' in media_url:
                base = account.base_url.replace('http://', '').replace('https://', '').rstrip('/')
                media_url = media_url.replace('localhost:3000', base)
                if not media_url.startswith('http'):
                    media_url = 'http://' + media_url

            vals = {
                'account_id': account.id,
                'partner_id': partner.id,
                'chat_id': chat_id,
                'wa_msg_id': wa_id,
                'direction': 'out' if msg.get('fromMe') else 'in',
                'sender_name': (msg.get('notifyName') or msg.get('pushname')
                                or msg.get('_data', {}).get('notifyName') or ''),
                'body': msg.get('body') or '',
                'media_type': media_type,
                'media_url': media_url,
                'msg_timestamp': msg_dt,
            }
            existing = self.search([
                ('account_id', '=', account.id),
                ('wa_msg_id', '=', wa_id),
            ], limit=1)
            if existing:
                existing.write(vals)
            else:
                self.create(vals)
        return len(messages or [])
