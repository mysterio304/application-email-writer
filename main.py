"""
Internship Email Automation Script
====================================
Parses the job publications HTML page and sends personalized
application emails to each company's contact person via Gmail.

SETUP (one-time):
1. Install dependencies:
       pip install beautifulsoup4
2. Enable Gmail App Password:
       - Go to https://myaccount.google.com/security
       - Enable 2-Step Verification (if not already)
       - Go to "App passwords" → create one for "Mail"
       - Paste the 16-character password into GMAIL_APP_PASSWORD below
3. Fill in YOUR_* constants below (your name, email, student ID, etc.)
4. Attach your CV/résumé file at ATTACHMENT_PATH (or set to None)
5. Run in DRY_RUN = True mode first to preview all emails
6. Set DRY_RUN = False to actually send
"""

import smtplib
import ssl
import time
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
#  CONFIGURATION — fill these in before running
# ─────────────────────────────────────────────

GMAIL_ADDRESS    = ""
GMAIL_APP_PASSWORD = ""

# Your personal details (used in the email body)
YOUR_NAME        = ""
YOUR_STUDENT_ID  = ""
YOUR_PROGRAMME   = ""
YOUR_YEAR        = "Year ..."
YOUR_PHONE       = ""

ATTACHMENT_PATH  = "CV_PATH.pdf"

HTML_FILE_PATH   = "HTML_PAGE.html"

# Set True only after verifying with DRY_RUN = True first
DRY_RUN          = True

SEND_DELAY_SEC   = 3

# ─────────────────────────────────────────────
#  EMAIL TEMPLATE
#  Available placeholders:
#    {contact_name}
#    {company_name}
#    {post_title}
#    {post_code}
#    {your_name}
#    {your_student_id}
#    {your_programme}
#    {your_year}
#    {your_phone}
# ─────────────────────────────────────────────

EMAIL_SUBJECT_TEMPLATE = (
    "Internship Application – {post_title} at {company_name} – {your_name}"
)

EMAIL_BODY_TEMPLATE = """\
To Whom It May Concern,

...

Yours faithfully,
{your_name}
{your_programme} | {your_year}
Phone: {your_phone}
Email: {sender_email}
"""

# ─────────────────────────────────────────────
#  DATA MODEL
# ─────────────────────────────────────────────

@dataclass
class Position:
    number: int
    company_name: str
    code: str
    post_title: str
    contact_person: str
    contact_email: str
    position_label: str = ""

# ─────────────────────────────────────────────
#  PARSER
# ─────────────────────────────────────────────

def parse_positions(html_source: str) -> list[Position]:
    """Extract all positions from the PMS HTML page."""
    soup = BeautifulSoup(html_source, "html.parser")
    positions = []

    for block in soup.find_all("div", class_="module-shadow"):
        h5 = block.find("h5")
        label = h5.get_text(strip=True) if h5 else ""

        rows = block.find_all("tr")
        data = {}
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True).rstrip(":")
                val = cells[1].get_text(strip=True)
                data[key] = val

        company  = data.get("Company Name", "").strip()
        code     = data.get("Code", "").strip()
        title    = data.get("Post Title", "").strip()
        contact  = data.get("Contact Person", "").strip()
        email    = data.get("Contact Person E-mail", "").strip()

        if not email or "@" not in email:
            logging.warning(f"Skipping {label} ({company}) — no valid email found.")
            continue

        num = 0
        for part in label.split():
            if part.isdigit():
                num = int(part)
                break

        positions.append(Position(
            number=num,
            company_name=company,
            code=code,
            post_title=title,
            contact_person=contact,
            contact_email=email,
            position_label=label,
        ))

    return positions

# ─────────────────────────────────────────────
#  EMAIL BUILDER
# ─────────────────────────────────────────────

def build_email(pos: Position) -> MIMEMultipart:
    subject = EMAIL_SUBJECT_TEMPLATE.format(
        post_title=pos.post_title,
        company_name=pos.company_name,
        your_name=YOUR_NAME,
    )
    body = EMAIL_BODY_TEMPLATE.format(
        company_name=pos.company_name,
        post_title=pos.post_title,
        post_code=pos.code,
        your_name=YOUR_NAME,
        your_student_id=YOUR_STUDENT_ID,
        your_programme=YOUR_PROGRAMME,
        your_year=YOUR_YEAR,
        your_phone=YOUR_PHONE,
        sender_email=GMAIL_ADDRESS,
    )

    msg = MIMEMultipart()
    msg["From"]    = f"{YOUR_NAME} <{GMAIL_ADDRESS}>"
    msg["To"]      = pos.contact_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # Attach CV
    if ATTACHMENT_PATH and os.path.isfile(ATTACHMENT_PATH):
        with open(ATTACHMENT_PATH, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        filename = os.path.basename(ATTACHMENT_PATH)
        part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
        msg.attach(part)
    else:
        logging.warning(
            f"CV file not found at '{ATTACHMENT_PATH}' — email will be sent WITHOUT attachment."
        )

    return msg

# ─────────────────────────────────────────────
#  SENDER
# ─────────────────────────────────────────────

def send_emails(positions: list[Position]):
    # Deduplicate: one email per unique (company_name, post_title, contact_email).
    # If only the Code differs, it's treated as the same job — skip duplicates.
    seen: dict[tuple, Position] = {}
    skipped = 0
    for pos in positions:
        key = (pos.company_name.lower(), pos.post_title.lower(), pos.contact_email.lower())
        if key not in seen:
            seen[key] = pos
        else:
            logging.info(
                f"SKIPPED duplicate: {pos.company_name} | {pos.post_title} "
                f"| {pos.contact_email} (Code {pos.code} — already queued as "
                f"{seen[key].code})"
            )
            skipped += 1

    unique_positions = list(seen.values())

    logging.info(f"\nTotal positions parsed : {len(positions)}")
    logging.info(f"Skipped (same job, diff code): {skipped}")
    logging.info(f"Emails to send         : {len(unique_positions)}")
    logging.info(f"Dry-run mode           : {DRY_RUN}\n")

    if DRY_RUN:
        print("=" * 60)
        print("DRY RUN — no emails will be sent. Preview below:")
        print("=" * 60)

    sent_ok, sent_fail = 0, 0
    context = ssl.create_default_context()

    smtp_conn = None
    if not DRY_RUN:
        smtp_conn = smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context)
        smtp_conn.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

    for i, pos in enumerate(unique_positions, 1):
        msg = build_email(pos)
        preview = (
            f"[{i}/{len(unique_positions)}] "
            f"To: {pos.contact_email} | "
            f"{pos.company_name} | "
            f"{pos.code}"
        )
        if DRY_RUN:
            print(f"\n{preview}")
            print(f"  Subject : {msg['Subject']}")
            print(f"  Body preview: {msg.get_payload(0).get_payload()[:120].strip()}...")
        else:
            try:
                smtp_conn.sendmail(GMAIL_ADDRESS, pos.contact_email, msg.as_string())
                logging.info(f"SENT     {preview}")
                sent_ok += 1
                time.sleep(SEND_DELAY_SEC)
            except Exception as e:
                logging.error(f"FAILED   {preview} — {e}")
                sent_fail += 1

    if smtp_conn:
        smtp_conn.quit()

    if not DRY_RUN:
        print(f"\nDone. Sent: {sent_ok}  Failed: {sent_fail}")
    else:
        print(f"\n{'=' * 60}")
        print(f"Dry run complete. {len(unique_positions)} emails previewed ({skipped} duplicates skipped).")
        print("Set DRY_RUN = False to send for real.")

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler("email_log.txt"),
            logging.StreamHandler(),
        ],
    )

    # Load HTML — either from a saved file or paste raw HTML as a string
    if os.path.isfile(HTML_FILE_PATH):
        with open(HTML_FILE_PATH, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        print(f"ERROR: HTML file not found at '{HTML_FILE_PATH}'.")
        print("Save the PMS page as an HTML file and update HTML_FILE_PATH.")
        exit(1)

    positions = parse_positions(html)
    if not positions:
        print("No valid positions found. Check the HTML file.")
        exit(1)

    send_emails(positions)