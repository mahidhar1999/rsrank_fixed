import smtplib
from email.mime.text import MIMEText
import os

def send_email(subject, body):
    sender = os.getenv("MAIL_USER")
    password = os.getenv("MAIL_PASSWORD")
    receiver = os.getenv("MAIL_TO")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())