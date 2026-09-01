import html
import urllib.request
import urllib.error

from odoo import http
from odoo.http import request

_STYLE = """
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
       margin: 0; padding: 12px; color: #1f2937; background: #fff; }
h3 { margin: 0 0 8px; font-size: 15px; }
.muted { color: #6b7280; font-size: 12px; }
.tabs { display: flex; flex-wrap: wrap; gap: 4px; border-bottom: 1px solid #e5e7eb;
        margin-bottom: 8px; }
.tab { padding: 6px 12px; cursor: pointer; border: 1px solid transparent;
       border-bottom: none; border-radius: 6px 6px 0 0; font-size: 13px;
       background: #f3f4f6; }
.tab.active { background: #fff; border-color: #e5e7eb; font-weight: 600;
              border-bottom: 2px solid #25d366; }
.panel { display: none; }
.panel.active { display: block; }
.chat-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.chat-head .phone { color: #6b7280; font-size: 12px; }
.btn { cursor: pointer; border: 1px solid #25d366; background: #25d366;
       color: #fff; border-radius: 6px; padding: 4px 10px; font-size: 12px; }
.btn:disabled { opacity: .5; cursor: default; }
.status { font-size: 12px; color: #6b7280; }
.messages { max-height: 480px; overflow-y: auto; padding: 4px 0; }
.msg { display: flex; flex-direction: column; margin: 6px 0; }
.msg.out { align-items: flex-end; }
.msg .meta { font-size: 11px; color: #9ca3af; margin: 0 4px 2px; }
.msg .bubble { max-width: 75%; padding: 7px 10px; border-radius: 10px;
               white-space: pre-wrap; word-break: break-word; font-size: 13px; }
.msg.in .bubble { background: #f0f2f5; }
.msg.out .bubble { background: #dcf8c6; }
.empty { color: #9ca3af; font-size: 13px; padding: 12px 4px; }
"""


class WahaChatController(http.Controller):

    def _account(self):
        return request.env['waha.account'].sudo().search([('active', '=', True)], limit=1)

    def _contacts_for(self, partner):
        if partner.is_company:
            contacts = partner.child_ids.filtered(lambda p: p.phone)
            if partner.phone:
                contacts = partner | contacts
            return contacts
        return partner

    def _messages_html(self, contact):
        rows = request.env['waha.chat.message'].search([
            ('partner_id', '=', contact.id),
        ], limit=500, order='msg_timestamp asc')
        if not rows:
            return '<div class="empty">No messages cached. Click "Sync" to pull ' \
                   'history from WAHA.</div>'
        out = []
        for m in rows:
            ts = m.msg_timestamp.strftime('%Y-%m-%d %H:%M') if m.msg_timestamp else ''
            who = 'You' if m.direction == 'out' else (m.sender_name or 'Contact')
            body = html.escape(m.body or '', quote=True)
            media_html = ''
            if m.media_url:
                proxy_url = m.media_url
                if '/api/files/' in proxy_url:
                    file_part = proxy_url.split('/api/files/', 1)[1]
                    proxy_url = '/waha/file/%s' % file_part
                mt = (m.media_type or '').lower()
                if mt in ('image', 'photo', 'jpeg', 'png', 'gif', 'webp'):
                    media_html = '<div class="media"><img src="%s" style="max-width:100%%;border-radius:8px;"/></div>' % html.escape(proxy_url + '?v=' + str(int(m.msg_timestamp.timestamp()) if m.msg_timestamp else 0))
                elif mt in ('video',):
                    media_html = '<div class="media"><video src="%s" controls preload="metadata" style="max-width:100%%;border-radius:8px;max-height:400px;"></video></div>' % html.escape(proxy_url + '?v=' + str(int(m.msg_timestamp.timestamp()) if m.msg_timestamp else 0))
                elif mt in ('audio', 'ptt', 'audio/ogg', 'audio/mpeg'):
                    media_html = '<div class="media"><audio src="%s" controls style="width:100%%;"></audio></div>' % html.escape(proxy_url + '?v=' + str(int(m.msg_timestamp.timestamp()) if m.msg_timestamp else 0))
                elif mt in ('document', 'pdf', 'application/pdf'):
                    media_html = '<div class="media"><iframe src="%s" style="width:100%%;height:400px;border:1px solid #ccc;border-radius:8px;"></iframe></div>' % html.escape(proxy_url)
                else:
                    # Generic download button for any file type
                    media_html = '<div class="media"><a href="%s" target="_blank" style="color:#25d366;display:inline-flex;align-items:center;gap:6px;padding:8px 12px;background:#f0f2f5;border-radius:8px;text-decoration:none;"><span style="font-size:20px;">📄</span> %s</a></div>' % (html.escape(proxy_url), html.escape(m.body or 'Download'))
            content = media_html + ('<div class="text">%s</div>' % body if body else '')
            if not content:
                content = '<div class="text" style="color:#9ca3af;">[media message]</div>'
            out.append(
                '<div class="msg %s">'
                '<div class="meta">%s · %s</div>'
                '<div class="bubble">%s</div>'
                '</div>' % (m.direction, html.escape(who), html.escape(ts), content)
            )
        return '<div class="messages">%s</div>' % ''.join(out)

    def _render_html(self, partner, account, contacts):
        if not account:
            body = ('<div class="empty">No active WAHA account is configured. '
                    'Go to the <b>WhatsApp &rarr; WAHA Accounts</b> menu, create '
                    'one and click <b>Test Connection</b>.</div>')
            return ('<!doctype html><html><head><meta charset="utf-8">'
                    '<style>%s</style></head><body><h3>WhatsApp Chat &mdash; %s</h3>'
                    '%s</body></html>'
                    % (_STYLE, html.escape(partner.display_name), body))

        tabs = []
        panels = []
        idx = 0
        for c in contacts:
            cid = c.id
            phone = c.phone or '(no phone)'
            active = ' active' if idx == 0 else ''
            disabled = '' if (c.phone or c.name) else ' disabled'
            tabs.append(
                '<div class="tab%s" data-tab="%s" onclick="wahaShow(%s)">%s</div>'
                % (active, cid, cid, html.escape(c.name or c.display_name)))
            panels.append(
                '<div class="panel%s" id="panel-%s">'
                '<div class="chat-head">'
                '<strong>%s</strong><span class="phone">%s</span>'
                '<button class="btn" onclick="wahaSync(%s)" id="btn-%s"%s>Sync</button>'
                '<span class="status" id="status-%s"></span>'
                '</div>%s</div>'
                % (active, cid, html.escape(c.name or c.display_name),
                   html.escape(phone), cid, cid, disabled, cid,
                   self._messages_html(c))
            )
            idx += 1

        if not tabs:
            tabs_html = ''
            panels_html = '<div class="empty">This contact has no phone number.</div>'
        else:
            tabs_html = ''.join(tabs)
            panels_html = ''.join(panels)

        return ('<!doctype html><html><head><meta charset="utf-8">'
                '<style>%s</style></head><body>'
                '<h3>WhatsApp Chat &mdash; %s</h3>'
                '<div class="muted">Read-only view of WhatsApp history synced '
                'from WAHA. No messages are sent from Odoo.</div>'
                '<div class="tabs">%s</div>%s'
                '<script>%s</script>'
                '</body></html>'
                % (_STYLE, html.escape(partner.display_name), tabs_html,
                   panels_html, self._JS))

    _JS = """
    function wahaShow(id){
        document.querySelectorAll('.tab').forEach(function(t){
            t.classList.toggle('active', t.getAttribute('data-tab')==id);
        });
        document.querySelectorAll('.panel').forEach(function(p){
            p.classList.toggle('active', p.id==='panel-'+id);
        });
    }
    function wahaSync(id){
        var btn=document.getElementById('btn-'+id);
        var st=document.getElementById('status-'+id);
        if(btn){btn.disabled=true;}
        if(st){st.textContent='Syncing...';}
        fetch('/waha/sync/partner/'+id,{method:'POST',
            headers:{'Content-Type':'application/json'},body:'{}'})
        .then(function(r){
            if(!r.ok){return r.text().then(function(t){throw new Error('HTTP '+r.status+': '+t);});}
            return r.json();
        })
        .then(function(raw){
            var d = raw && raw.result ? raw.result : raw;
            if(st){st.textContent=d.ok?('Synced ('+d.count+')'):('Error: '+(d.error||'unknown'));}
            if(d.ok){setTimeout(function(){location.reload();},600);}
            else if(btn){btn.disabled=false;}
        })
        .catch(function(e){
            if(st){st.textContent='Error: '+(e.message||'unknown');}
            if(btn){btn.disabled=false;}
        });
    }
    """

    @http.route('/waha/chat/partner/<int:partner_id>', auth='user',
                type='http', csrf=False, website=False)
    def chat_partner(self, partner_id, **kw):
        partner = request.env['res.partner'].browse(partner_id).exists()
        if not partner:
            return request.make_response(
                '<p>Partner not found.</p>',
                headers=[('Content-Type', 'text/html; charset=utf-8')])
        account = self._account()
        contacts = self._contacts_for(partner)
        html_doc = self._render_html(partner, account, contacts)
        return request.make_response(
            html_doc, headers=[
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Content-Security-Policy', "default-src 'self' 'unsafe-inline' data: blob:; img-src 'self' http://192.168.18.89:3000 https://odoo.chenxingautomation.cn data: blob:; font-src 'self' data:;"),
            ])

    @http.route('/waha/sync/partner/<int:partner_id>', auth='none',
                type='jsonrpc', csrf=False, website=False)
    def sync_partner(self, partner_id, **kw):
        partner = request.env['res.partner'].sudo().browse(partner_id).exists()
        if not partner:
            return {'ok': False, 'error': 'Partner not found'}
        account = self._account()
        if not account:
            return {'ok': False, 'error': 'No active WAHA account configured'}
        try:
            count = account.sync_chat_tree(partner)
            return {'ok': True, 'count': count}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @http.route('/waha/file/<path:file_path>', auth='none',
                type='http', csrf=False, website=False)
    def proxy_file(self, file_path, **kw):
        account = self._account()
        if not account:
            return request.make_response('No WAHA account', status=404)
        base = account.base_url.rstrip('/')
        url = '%s/api/files/%s' % (base, file_path)
        api_key = account.api_key or ''
        try:
            req = urllib.request.Request(url)
            req.add_header('X-Api-Key', api_key)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            resp = opener.open(req, timeout=30)
            content = resp.read()
            content_type = resp.headers.get('Content-Type', 'application/octet-stream')
            return request.make_response(
                content,
                headers=[
                    ('Content-Type', content_type),
                    ('Content-Length', len(content)),
                    ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                    ('Pragma', 'no-cache'),
                    ('Content-Security-Policy', "default-src 'self' 'unsafe-inline' data: blob:; img-src 'self' http://192.168.18.89:3000 data: blob:;"),
                ])
        except urllib.error.HTTPError as e:
            return request.make_response('File not found', status=e.code)
        except Exception as e:
            return request.make_response('Error: %s' % str(e), status=500)
