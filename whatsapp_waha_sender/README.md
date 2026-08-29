# WhatsApp Sender (WAHA) — Odoo 19 Community

Send WhatsApp messages from **CRM leads, Sales Orders, Invoices (and Contacts)**
with reusable **templates** and **mass / bulk send**, by connecting Odoo to a
[WAHA](https://github.com/devlikeapro/waha) instance (open-source WhatsApp Web API).

This module is a **from-scratch, send-focused** integration. It does **not** patch
the Odoo Discuss frontend, so it is fully compatible with Odoo 19.

## Features

| Feature | Where |
|---|---|
| Send WhatsApp text / file from a document | "Send WhatsApp" button on CRM lead, Sales Order, Invoice, Contact forms |
| Reusable templates with `{{variables}}` | `waha.template` (Variables: `{{partner_id.name}}`, `{{name}}`, `{{amount_total}}`, `{{invoice_date}}`, …) |
| Mass / bulk send | List-view action menu → "Send WhatsApp (Mass)" for CRM / SO / Invoice / Contact |
| Invoice PDF attachment | Auto-generated when sending from an invoice |
| Sending log | `waha.message` records every send (success / failure) |
| Connection check | "Test Connection" button on the WAHA account |

## Install

1. Copy the `whatsapp_waha_sender/` folder into your Odoo **addons path**.
2. Restart Odoo, update the app list, and install **WhatsApp Sender (WAHA)**.
3. Dependencies (`crm`, `sale`, `account`) are standard and normally present.

## 1) Stand up WAHA

WAHA runs as a Docker container (or any host with Node). Example:

```bash
docker run -p 3000:3000 devlikeapro/waha
```

Open `http://<host>:3000/#/session/start`, create a session named `default`
(or whatever you set on the Odoo account), and **scan the QR code** with the
phone that will send the messages.

> WAHA Plus (paid) additionally supports Meta-approved template messages and
> multiple sessions. The community edition used here sends free-form text.

## 2) Configure the WAHA account in Odoo

Go to **WhatsApp → WAHA Accounts → New**:

- **Name**: anything, e.g. `Main WAHA`
- **WAHA Base URL**: `http://localhost:3000` (use the host reachable from Odoo)
- **API Key**: only if you set `WAHA_API_KEY` on the WAHA container
- **Session**: the session name you started in WAHA (default `default`)

Click **Test Connection** to verify Odoo can reach WAHA.

## 3) Create a template (optional)

Go to **WhatsApp → Templates → New**:

```
Hello {{partner_id.name}}, your order {{name}} total {{amount_total}} {{currency_id.name}} is ready.
```

Variables are resolved against the source document. Use `{{partner.field}}` to
reach partner fields.

## 4) Send

- **Single**: open a CRM lead / Sales Order / Invoice / Contact → click
  **Send WhatsApp**, pick the account, optionally a template, write the message
  (attach the invoice PDF for moves), click **Send**.
- **Mass**: in any of those list views, select rows → **Action → Send WhatsApp
  (Mass)**, pick account + template, click **Send to All**.

Phone numbers are converted to WAHA chat ids (`<international digits>@c.us`),
e.g. `+86 155 1097 9062` → `8615510979062@c.us`. Enter numbers in
international format (no `+`, country code included).

## Limitations (WhatsApp Web / WAHA community)

- You can only message numbers that are in the sending phone's **contacts**.
- Free-form messages to new contacts may be blocked by WhatsApp Web rules.
- For Meta-approved **template messages** (24h+ outreach) use WAHA Plus or a
  WABA provider; this module's "template" is a reusable text with variables.

## License

LGPL-3. Free to use and modify.
