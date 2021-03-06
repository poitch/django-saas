from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_multi_mail(subject_template_name, email_template_name,
                    context, from_email, to_email, html_email_template_name=None,
                    attachments=None, fail_silently=False):
    """
    Send a django.core.mail.EmailMultiAlternatives to `to_email`.
    """
    subject = render_to_string(subject_template_name, context)
    # Email subject *must not* contain newlines
    subject = ''.join(subject.splitlines())
    body = render_to_string(email_template_name, context)

    if not isinstance(to_email, list):
        to_email = [to_email]
    email_message = EmailMultiAlternatives(
        subject, body, from_email, to_email)
    if html_email_template_name is not None:
        html_email = render_to_string(html_email_template_name, context)
        email_message.attach_alternative(html_email, 'text/html')
    if attachments is not None:
        for attachment in attachments:
            email_message.attach(attachment['name'], attachment['content'], attachment['type'])
    email_message.send(fail_silently)
