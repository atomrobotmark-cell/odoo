{
    'name': 'WhatsApp Sender (WAHA)',
    'author': 'Atomrobot / Mark Liu',
    'summary': 'Send WhatsApp messages from CRM/Sales/Invoices and view chat history (WAHA)',
    'description': """
WhatsApp Sender connects Odoo 19 Community to a WAHA (WhatsApp Web API) instance and lets you send WhatsApp messages directly from business documents.

Features:
- Send WhatsApp text or file messages from CRM leads, Sales Orders and Invoices (a "Send WhatsApp" button is added to each form).
- Reusable message templates with {{variable}} substitution (e.g. {{partner_id.name}}, {{name}}, {{amount_total}}, {{invoice_date}}).
- Mass / bulk send from the list view action menu (server action) for CRM leads, Sales Orders, Invoices and Contacts.
- Optional invoice PDF attachment when sending from an invoice.
- Message sending log (waha.message) for traceability.
- "Test Connection" button on the WAHA account to verify reachability.

Read-only chat viewer:
- A "WhatsApp Chat" tab on Contact, CRM Lead, Sales Order and Invoice forms shows the WhatsApp conversation history (synced from WAHA into Odoo).
- On a company contact the tab shows one sub-tab per related contact so you can switch between them.
- History is cached in Odoo (waha.chat.message) so it is viewable even when WAHA is offline, and is searchable. Click "Sync" inside the panel to refresh from WAHA. No messages are sent from the viewer.

Backend: WAHA (https://github.com/devlikeapro/waha) running locally or remotely. This module does not require the Odoo Discuss patch, so it is fully compatible with Odoo 19.

Note: WhatsApp Web (WAHA community) can only message numbers that are in the phone's contacts and is subject to WhatsApp Web limits. For Meta-approved template messages use WAHA Plus / a WABA provider.
""",
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Communication',
    'website': 'https://github.com/devlikeapro/waha',
    'depends': ['base', 'crm', 'sale', 'account', 'mail'],
    'data': [
        'views/waha_account_views.xml',
        'views/waha_composer_views.xml',
        'views/integration_views.xml',
        'views/waha_chat_views.xml',
        'data/server_actions.xml',
    ],
    'post_init_hook': 'create_access_rights',
    'assets': {
        'web.assets_backend': [
            'whatsapp_waha_sender/static/src/js/waha_chat_iframe.js',
            'whatsapp_waha_sender/static/src/xml/waha_chat_iframe.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
