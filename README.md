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
