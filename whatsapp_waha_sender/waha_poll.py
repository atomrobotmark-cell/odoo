#!/usr/bin/env python3
"""
WAHA poller v14 - Uses SAME matching logic as Odoo Sync button.
Also supports historical sync (--history flag).
"""
import json
import re
import sys
import time
import urllib.request
from datetime import datetime

WAHA_URL = "http://192.168.18.89:3000"
WAHA_KEY = "atomrobot_waha_2024"
PG = {"host": "172.24.0.20", "port": 5432, "dbname": "atomrobot", "user": "mark", "password": "mark.lennon"}

import psycopg2


def api_get(path, timeout=8):
    req = urllib.request.Request(f"{WAHA_URL}{path}")
    req.add_header("X-Api-Key", WAHA_KEY)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def _ts(ts):
    if not ts:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def norm(s):
    """Normalize for matching: lowercase, remove non-alphanumeric."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def find_partner_for_chat(chat_name, chat_digits, partner_index):
    """Find Odoo partner for a WAHA chat.
    
    Matching strategy:
    1. Phone digit suffix match (for @c.us format)
    2. Name contains match (one name contains the other)
    3. Fallback: fuzzy name match (first N chars, common words)
    """
    if not chat_name and not chat_digits:
        return None

    chat_name_n = norm(chat_name) if chat_name else ""

    # Strategy 1: Phone digit suffix match
    if chat_digits and len(chat_digits) >= 8:
        for pid, pdata in partner_index.items():
            p_digits = pdata.get("digits", "")
            if p_digits and len(p_digits) >= 8:
                if chat_digits.endswith(p_digits[-10:]) or p_digits.endswith(chat_digits[-10:]):
                    return pid

    # Strategy 2: Name contains match (same as Odoo Sync)
    if chat_name_n and len(chat_name_n) >= 3:
        for pid, pdata in partner_index.items():
            p_name_n = pdata.get("name_norm", "")
            if p_name_n and len(p_name_n) >= 3:
                if chat_name_n in p_name_n or p_name_n in chat_name_n:
                    return pid

    # Strategy 3: Fuzzy name match (fallback)
    # Match if first 4+ chars match, or common words match
    if chat_name_n and len(chat_name_n) >= 4:
        for pid, pdata in partner_index.items():
            p_name_n = pdata.get("name_norm", "")
            if not p_name_n or len(p_name_n) < 4:
                continue
            # First 4 chars match
            if chat_name_n[:4] == p_name_n[:4]:
                return pid
            # Common word match (e.g., "dhl" in "DHL Express")
            chat_words = set(re.findall(r'[a-z]{3,}', chat_name_n))
            partner_words = set(re.findall(r'[a-z]{3,}', p_name_n))
            if chat_words and partner_words and chat_words & partner_words:
                return pid

    # Strategy 4: Message-based fallback (fetch messages, extract phone numbers)
    # This is slower but more reliable for @lid format chats
    return None  # Will be handled in main loop with message fetch


def find_partner_from_messages(cid, partner_index, api_get):
    """Fallback: fetch messages and try to match by phone number in message body.
    
    WAHA @lid chats don't have phone numbers in the chat ID, but phone numbers
    might appear in message bodies (e.g., "My number is +62...").
    """
    try:
        msgs = api_get(f"/api/default/chats/{cid}/messages?limit=5", timeout=10)
    except Exception:
        return None
    
    if not msgs:
        return None
    
    # Extract all phone numbers from messages
    all_numbers = set()
    for m in msgs:
        body = m.get("body", "") or ""
        # Find phone-like patterns (8+ digits, possibly with + prefix)
        found = re.findall(r'[\+]?\d{8,15}', body)
        all_numbers.update(found)
    
    # Also check the 'from' field for @c.us format (our own messages)
    for m in msgs:
        fr = m.get("from", "")
        if "@c.us" in fr:
            digits = re.sub(r"\D", "", fr.split("@")[0])
            if digits:
                all_numbers.add(digits)
    
    # Match extracted numbers to partners
    for num in all_numbers:
        num_digits = re.sub(r"\D", "", num)
        if len(num_digits) < 8:
            continue
        for pid, pdata in partner_index.items():
            p_digits = pdata.get("digits", "")
            if p_digits and len(p_digits) >= 8:
                if num_digits.endswith(p_digits[-10:]) or p_digits.endswith(num_digits[-10:]):
                    return pid
    
    return None


def main():
    history_mode = "--history" in sys.argv
    history_limit = 100  # messages per chat in history mode

    t0 = time.time()
    conn = psycopg2.connect(**PG)
    cur = conn.cursor()
    cur.execute("SELECT id FROM waha_account WHERE active = true LIMIT 1")
    row = cur.fetchone()
    if not row:
        print("No WAHA account")
        return
    aid = row[0]

    # Load existing msg IDs
    cur.execute("SELECT wa_msg_id FROM waha_chat_message")
    existing = set(r[0] for r in cur.fetchall())

    # Build partner index (same data structure as Odoo Sync)
    cur.execute("SELECT id, name, phone FROM res_partner WHERE name IS NOT NULL AND name != ''")
    partner_index = {}
    for pid, name, phone in cur.fetchall():
        digits = re.sub(r"\D", "", phone or "")
        partner_index[pid] = {
            "name": name,
            "name_norm": norm(name),
            "digits": digits,
            "phone": phone,
        }

    # Pre-load chat_id -> partner_id from existing messages
    cur.execute("SELECT DISTINCT chat_id, partner_id FROM waha_chat_message WHERE partner_id IS NOT NULL")
    chat_partner = {}
    for cid, pid in cur.fetchall():
        chat_partner[cid] = pid

    # Get WAHA chat list
    chats = api_get("/api/default/chats?limit=600", timeout=30)

    if history_mode:
        # History mode: process ALL individual chats
        target_chats = []
        for ch in chats:
            cid = ch.get("id", {}).get("_serialized", "")
            if not cid or "@g.us" in cid or "@broadcast" in cid:
                continue
            target_chats.append((cid, ch.get("name", "")))
        print(f"{time.strftime('%H:%M:%S')} History mode: {len(target_chats)} chats to process")
    else:
        # Normal mode: only recent chats (< 1 hour)
        cutoff = time.time() - 86400
        target_chats = []
        for ch in chats:
            cid = ch.get("id", {}).get("_serialized", "")
            if not cid or "@g.us" in cid or "@broadcast" in cid:
                continue
            lm = ch.get("lastMessage", {})
            if not isinstance(lm, dict):
                continue
            lm_ts = lm.get("timestamp", 0)
            if lm_ts and lm_ts >= cutoff:
                target_chats.append((cid, ch.get("name", "")))

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    nc = 0
    checked = 0
    errors = 0
    matched = 0
    unmatched = 0

    for cid, chat_name in target_chats:
        checked += 1

        # Find partner_id using SAME logic as Odoo Sync
        pid = chat_partner.get(cid)
        if not pid:
            digits_chat = re.sub(r"\D", "", cid.split("@")[0])
            pid = find_partner_for_chat(chat_name, digits_chat, partner_index)
            if not pid:
                # Fallback: try to match from messages
                pid = find_partner_from_messages(cid, partner_index, api_get)
            if pid:
                chat_partner[cid] = pid
                matched += 1
            else:
                unmatched += 1

        # Fetch messages
        limit = history_limit if history_mode else 10
        try:
            msgs = api_get(f"/api/default/chats/{cid}/messages?limit={limit}", timeout=10)
        except Exception:
            errors += 1
            continue

        if not msgs:
            continue

        for m in msgs:
            wid = m.get("id", "")
            if isinstance(wid, dict):
                wid = wid.get("_serialized", str(wid))
            wid = str(wid)
            if wid in existing:
                continue

            body = m.get("body", "") or ""
            fm = m.get("fromMe", False)
            mt = m.get("type", "text")
            sender_name = m.get("sender", {}).get("pushname", "") if not fm else ""

            cur.execute(
                """INSERT INTO waha_chat_message
                (account_id, partner_id, chat_id, wa_msg_id, direction, sender_name, body,
                 media_type, msg_timestamp, create_date, write_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    aid, pid, cid, wid,
                    "out" if fm else "in",
                    sender_name, body, mt,
                    _ts(m.get("timestamp")),
                    now, now,
                ),
            )
            existing.add(wid)
            nc += 1

        # Commit periodically in history mode
        if history_mode and checked % 50 == 0:
            conn.commit()
            elapsed = time.time() - t0
            print(f"  ... {checked}/{len(target_chats)} chats, {nc} new, {matched} matched, {unmatched} unmatched ({elapsed:.0f}s)")

    conn.commit()
    cur.close()
    conn.close()
    elapsed = time.time() - t0
    mode = "History" if history_mode else "Poll"
    print(
        f"{time.strftime('%H:%M:%S')} {mode}: {len(target_chats)} chats, checked={checked}, new={nc}, "
        f"matched={matched}, unmatched={unmatched}, errors={errors} ({elapsed:.1f}s)"
    )


if __name__ == "__main__":
    main()
