#!/usr/bin/env python3
"""
Profile-based Email Sender
Sends offer letters using company-specific email credentials
"""

import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
import sys

def load_profile(profile_name):
    """Load company profile configuration"""
    profile_path = Path('profiles') / profile_name / 'config.json'
    
    if not profile_path.exists():
        print(f"❌ Profile '{profile_name}' not found!")
        print(f"Available profiles: melange, urbanmistrii, decoarte")
        sys.exit(1)
    
    with open(profile_path, 'r') as f:
        return json.load(f)

def send_offer_email(candidate_data_path, pdf_path, profile, recipient_override=None):
    """Send offer letter PDF via email using profile credentials"""
    
    # Load candidate data
    with open(candidate_data_path, 'r') as f:
        data = json.load(f)
    
    recipient_email = recipient_override if recipient_override else data.get('email')
    candidate_name = data.get('name')
    position = data.get('position')
    
    sender_email = profile['email']
    sender_password = profile['app_password']
    company_name = profile['company_name']
    
    if sender_password == "TO_BE_CONFIGURED":
        print(f"❌ Email credentials not configured for {company_name}")
        print(f"💡 Update the app_password in profiles/{profile['email'].split('@')[0]}/config.json")
        return False
    
    # Create email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = f"Offer Letter - {position} Position at {company_name}"
    
    # Email body (Beautified and professional)
    body = f"""Dear {candidate_name},

It is with great pleasure that we extend this formal offer of employment for the position of {position} at {company_name}.

Based on our recent interactions and your impressive background, we believe your skills and perspective will be a valuable addition to our team.

Please find your offer letter attached to this communication. We kindly request that you review the terms and conditions outlined in the document.

To proceed with your acceptance, please follow these steps:
1. Thoroughly review the attached offer letter.
2. Sign the document (either by printing and scanning or using a digital signature).
3. Return the signed copy to this email address.

Should you have any questions or require further clarification regarding any aspect of this offer, please do not hesitate to reach out to us.

We are excited about the possibility of you joining {company_name} and contributing to our shared success.

{profile['email_signature']}
"""
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach PDF
    with open(pdf_path, 'rb') as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=Offer_Letter_{candidate_name.replace(" ", "_")}.pdf')
        msg.attach(part)
    
    # Send email
    try:
        print(f"📧 Connecting to Gmail SMTP server...")
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        
        print(f"🔐 Logging in as {sender_email}...")
        server.login(sender_email, sender_password)
        
        print(f"📤 Sending email to {recipient_email}...")
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email sent successfully to {candidate_name} ({recipient_email})")
        return True
        
    except Exception as e:
        print(f"❌ Email failed: {e}")
        return False

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 send_email.py <profile> <candidate.json> [--to recipient@email.com]")
        print("\nProfiles:")
        print("  melange      - The Melange Studio")
        print("  urbanmistrii - Urban Mistrii")
        print("  decoarte     - Deco Arte")
        print("\nExample:")
        print("  python3 send_email.py melange examples/sample_candidate.json --to reviewer@email.com")
        sys.exit(1)
    
    profile_name = sys.argv[1]
    candidate_file = sys.argv[2]
    
    recipient_override = None
    if '--to' in sys.argv:
        try:
            recipient_override = sys.argv[sys.argv.index('--to') + 1]
        except IndexError:
            print("❌ Error: --to requires an email address")
            sys.exit(1)
    
    # Load profile
    print(f"📋 Loading profile: {profile_name}")
    profile = load_profile(profile_name)
    
    # Load candidate data
    with open(candidate_file, 'r') as f:
        data = json.load(f)
    
    # Find PDF
    candidate_name = data['name'].replace(' ', '_')
    pdf_path = Path('output') / profile_name / f'offer_letter_{candidate_name}.pdf'
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        print("💡 Generate the offer letter first using:")
        print(f"   python3 generate_offer.py {profile_name} {candidate_file}")
        sys.exit(1)
    
    print(f"📄 Found PDF: {pdf_path}")
    print(f"🏢 Company: {profile['company_name']}")
    if recipient_override:
        print(f"🎯 Overriding recipient: {recipient_override}")
    
    send_offer_email(candidate_file, pdf_path, profile, recipient_override)

if __name__ == "__main__":
    main()
