from abc import ABC, abstractmethod

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.http import HttpRequest

from saas.models import BillingEvent

User = get_user_model()

class AbstractSaasMailer(ABC):
    @classmethod
    @abstractmethod
    def on_payment_succeeded(cls, request:HttpRequest, user:User, billing:BillingEvent, stripe_object:str):
         pass

    @classmethod
    @abstractmethod
    def on_payment_failed(cls, request:HttpRequest, user:User, billing:BillingEvent, stripe_object:str):
        pass

    @classmethod
    @abstractmethod
    def on_payment_action_required(cls, request:HttpRequest, user:User, stripe_object:str):
        pass

    @classmethod
    @abstractmethod
    def on_invoice_incoming(cls, request:HttpRequest, user:User, stripe_object:str):
        pass

    @classmethod
    @abstractmethod
    def on_trial_vill_end(cls, request:HttpRequest, user:User, stripe_object:str):
         pass

    @classmethod
    @abstractmethod
    def on_activating(cls, request:HttpRequest, user:User, uid: str, token: str):
        pass


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
