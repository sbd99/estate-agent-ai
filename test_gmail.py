from gmail_handler import get_unread_emails

print("Authenticating with Gmail...")
emails = get_unread_emails(max_results=10)

if not emails:
    print("No unread emails found.")
else:
    print(f"Found {len(emails)} unread email(s):\n")
    for i, email in enumerate(emails, start=1):
        print(f"--- Email {i} ---")
        print(f"From:    {email.sender_name} <{email.sender_email}>")
        print(f"Subject: {email.subject}")
        print(f"Body:\n{email.body[:500]}{'...' if len(email.body) > 500 else ''}")
        print()
