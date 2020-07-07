import stripe

from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import login, get_user_model
from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View, TemplateView
from django.views.generic.edit import FormView
from saas.forms import CreateUserForm
from saas.mailer import send_multi_mail
from saas.models import StripeInfo, BillingEvent, StripeEvent

User = get_user_model()

class CsrfExemptMixin(object):
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(CsrfExemptMixin, self).dispatch(*args, **kwargs)


class RegisterView(FormView):
    email_template_name = 'registration/activation_email.txt'
    extra_email_context = None
    form_class = CreateUserForm
    from_email = None
    html_email_template_name = None
    subject_template_name = 'registration/activation_subject.txt'
    success_url = reverse_lazy('activating')
    template_name = 'contact.html'
    title = _('Register')
    token_generator = default_token_generator

    def form_valid(self, form):
        opts = {
            'use_https': self.request.is_secure(),
            'token_generator': self.token_generator,
            'from_email': self.from_email,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': self.extra_email_context,
        }
        form.save(**opts)

        messages.success(
            self.request,
            'Account was created successfully. Please, check your email to continue the registration process.')

        return super().form_valid(form)


class ActivatingView(TemplateView):
    template_name = 'registration/activating.html'


class ActivateView(View):
    success_url = reverse_lazy('index')
    failure_url = reverse_lazy('login')
    expired_token_template_name = 'registration/activating.html'

    def get(self, request, uidb64, token):
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        if (user is not None and default_token_generator.check_token(user, token)):
            user.is_active = True
            user.save()
            login(request, user)
            messages.add_message(request, messages.INFO,
                                 'Account activated.')
            return redirect(self.success_url)
        else:
            messages.add_message(
                request,
                messages.WARNING,
                'Link Expired. Contact admin to activate your account.')
            return render(request, self.expired_token_template_name)

        return redirect(self.failure_url)


class StripeViewMixin:
    @property
    def stripe(self):
        stripe.api_key = settings.STRIPE_API_KEY
        return stripe

    def stripe_customer_for_user(self, user):
        try:
            info = user.stripeinfo
            try:
                customer = stripe.Customer.retrieve(info.customer_id)
                if 'deleted' not in customer:
                    return customer
            except stripe.error.InvalidRequestError:
                pass
        except User.stripeinfo.RelatedObjectDoesNotExist:
            pass
        return self.stripe_customer_by_email(user.email)

    def stripe_customer_by_email(self, email):
        results = self.stripe.Customer.list(
            email=email,
        )
        for customer in results['data']:
            if 'deleted' not in customer:
                return customer
        return None

    def stripe_customer_card_subscription(self, user):
        customer = self.stripe_customer_for_user(user)
        card = None
        subscription = None
        if customer is None:
            return None, None, None
        if len(customer['sources']['data']) > 0:
            card = customer['sources']['data'][0]
        if len(customer['subscriptions']['data']) > 0:
            subscription = customer['subscriptions']['data'][0]
        return customer, card, subscription



class SubscribeView(LoginRequiredMixin, StripeViewMixin, View):
    template_name = 'subscription/subscribe.html'
    success_url = reverse_lazy('index')

    def get(self, request, *args, **kwargs):
        plans = self.stripe.Plan.list()
        context = {}
        context['plans'] = plans
        context['STRIPE_PUBLISHABLE_API_KEY'] = settings.STRIPE_PUBLISHABLE_API_KEY
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        token = request.POST.get('stripeToken', None)
        customer = self.stripe_customer_by_email(request.user.email)
        if customer is not None:
            customer = self.stripe.Customer.modify(
                customer['id'],
                source=token,
            )
        else:
            customer = self.stripe.Customer.create(
                source=token,
                email=request.user.email,
            )
        subscription = self.stripe.Subscription.create(
            customer=customer['id'],
            trial_from_plan=True,
            items=[
                {
                    "plan": request.POST.get('plan'),
                }
            ]
        )

        info = None
        try:
            info = StripeInfo.objects.get(user=request.user)
            info.customer_id = customer['id']
        except StripeInfo.DoesNotExist:
            info = StripeInfo.objects.create(
                user=request.user,
                customer_id=customer['id']
            )

        info.subscription_id = subscription['id']
        info.subscription_end = datetime.fromtimestamp(
            int(subscription['current_period_end']))
        info.save()

        return redirect(self.success_url)


class StripeWebhook(View, CsrfExemptMixin):
    from_email = None
    # Payment Succeeded
    payment_succeeded_email_template_name = None
    payment_succeeded_subject_template_name = None
    html_payment_succeeded_email_template_name = None
    # Payment Failed
    payment_failed_email_template_name = None
    payment_failed_subject_template_name = None
    html_payment_failed_email_template_name = None
    # Payment Action Required
    payment_action_required_email_template_name = None
    payment_action_required_subject_template_name = None
    html_payment_action_required_email_template_name = None
    # Invoice Incoming
    invoice_incoming_email_template_name = None
    invoice_incoming_subject_template_name = None
    html_invoice_incoming_email_template_name = None

    def post(self, request):
        payload = request.body
        sig_header = request.META['HTTP_STRIPE_SIGNATURE']
        event = None

        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError as e:
            # Invalid payload
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            return HttpResponse(status=400)

        stripe_object = event['data']['object']
        customer_id = None
        user = None
        info = None

        if 'customer' in stripe_object:
            customer_id = stripe_object['customer']
            try:
                info = StripeInfo.objects.get(customer_id=customer_id)
                user = info.user
            except StripeInfo.DoesNotExist:
                pass

        # Record Event
        StripeEvent.objects.create(
            event=event['type'],
            object=stripe_object,
            customer_id=customer_id,
            user=user,
        )

        if event['type'] == 'invoice.payment_succeeded':
            if user is not None:
                billing = BillingEvent.objects.create(
                    user=user,
                    stripe_object=stripe_object,
                )
                # Do not email trial emails where amount_due and amount_paid are both 0
                if stripe_object['amount_due'] != 0 or stripe_object['amount_paid'] != 0:
                    self.on_payment_succeeded(
                        request, user, billing, stripe_object)
        elif event['type'] == 'invoice.payment_failed':
            if user is not None:
                billing = BillingEvent.objects.create(
                    user=user,
                    success=False,
                    stripe_object=stripe_object,
                )
                self.on_payment_failed(request, user, billing, stripe_object)
        elif event['type'] == 'invoice.payment_action_required':
            if user is not None:
                pass
                self.on_payment_action_required(request, user, stripe_object)
        elif event['type'] == 'invoice.incoming':
            if user is not None:
                pass
                self.on_invoice_incoming(request, user, stripe_object)
        elif event['type'] == 'customer.subscription.updated':
            if user is not None:
                info.subscription_id = stripe_object['id']
                info.subscription_end = stripe_object['current_period_end']
                info.save()
        elif event['type'] == 'customer.subscription.trial_will_end':
            # Need to update user
            pass
        elif event['type'] == 'customer.subscription.deleted':
            # Need to update user
            if user is not None:
                info.subscription_id = None
                info.subscription_end = None
                info.save()
        elif event['type'] == 'customer.subscription.created':
            if user is not None:
                info.subscription_id = stripe_object['id']
                info.subscription_end = stripe_object['current_period_end']
                info.save()

        return HttpResponse(status=200)

    def on_payment_succeeded(self, request, user, billing, stripe_object):
        if self.payment_succeeded_email_template_name is None or self.payment_succeeded_subject_template_name is None:
            return
        context = {
            'request': request,
            'user': user,
            'billing': billing,
            'payment': stripe_object,
            'protocol': request.scheme,
            'username': self.cleaned_data.get('username'),
            'domain': request.META['HTTP_HOST'],
        }
        send_multi_mail(self.payment_succeeded_subject_template_name, self.payment_succeeded_email_template_name, context,
                        self.from_email, user.email, html_email_template_name=self.html_payment_succeeded_email_template_name)

    def on_payment_failed(self, request, user, billing, stripe_object):
        if self.payment_failed_email_template_name is None or self.payment_failed_subject_template_name is None:
            return
        context = {
            'request': request,
            'user': user,
            'billing': billing,
            'payment': stripe_object,
            'protocol': request.scheme,
            'username': self.cleaned_data.get('username'),
            'domain': request.META['HTTP_HOST'],
        }
        send_multi_mail(self.payment_failed_subject_template_name, self.payment_failed_email_template_name, context,
                        self.from_email, user.email, html_email_template_name=self.html_payment_failed_email_template_name)

    def on_payment_action_required(self, request, user, stripe_object):
        if self.payment_action_required_email_template_name is None or self.payment_action_required_subject_template_name is None:
            return
        context = {
            'request': request,
            'user': user,
            'payment': stripe_object,
            'protocol': request.scheme,
            'username': self.cleaned_data.get('username'),
            'domain': request.META['HTTP_HOST'],
        }
        send_multi_mail(self.payment_action_required_subject_template_name, self.payment_action_required_email_template_name, context,
                        self.from_email, user.email, html_email_template_name=self.html_payment_action_required_email_template_name)

    def on_invoice_incoming(self, request, user, stripe_object):
        if self.invoice_incoming_email_template_name is None or self.invoice_incoming_subject_template_name is None:
            return
        context = {
            'request': request,
            'user': user,
            'payment': stripe_object,
            'protocol': request.scheme,
            'username': self.cleaned_data.get('username'),
            'domain': request.META['HTTP_HOST'],
        }
        send_multi_mail(self.invoice_incoming_subject_template_name, self.invoice_incoming_email_template_name, context,
                        self.from_email, user.email, html_email_template_name=self.html_invoice_incoming_email_template_name)


class BillingView(View):
    template_name = 'subscription/billing.html'

    def get(self, request, billing_id):
        billing = get_object_or_404(BillingEvent, pk=billing_id)
        if billing.user != request.user:
            raise Http404

        context = {}
        context['billing'] = billing

        return render(request, self.template_name, context)


class UpdatePaymentView(LoginRequiredMixin, StripeViewMixin, View):
    template_name = 'subscription/update_payment.html'
    success_url = reverse_lazy('index')

    def get(self, request, *args, **kwargs):
        context = {}
        context['STRIPE_PUBLISHABLE_API_KEY'] = settings.STRIPE_PUBLISHABLE_API_KEY
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        customer = self.stripe_customer_for_user(request.user)
        if customer is not None:
            customer = self.stripe.Customer.modify(
                customer['id'],
                source=request.POST.get('stripeToken')
            )
            self.stripe.Subscription.modify(
                request.user.stripeinfo.subscription_id,
                default_source=customer['sources']['data'][0]['id'],
            )
        return redirect(self.success_url)

class SubscriptionView(LoginRequiredMixin, StripeViewMixin, TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer, card, subscription = self.stripe_customer_card_subscription(self.request.user)
        for billing in BillingEvent.objects.filter(user=self.request.user).order_by('-created_at'):
            context['billing'].append(billing)

        context['customer'] = customer
        context['card'] = card
        context['subscription'] = subscription
        return context

class CancelSubscriptionView(LoginRequiredMixin, StripeViewMixin, View):
    success_url = reverse_lazy('index')

    def get(self, request):
        _, _, subscription = self.stripe_customer_card_subscription(self.request.user)
        if subscription is not None:
            cancel_at_period_end = settings.SAAS_CANCEL_SUBSCRIPTION_AT_PERIOD_END if hasattr(settings, 'SAAS_CANCEL_SUBSCRIPTION_AT_PERIOD_END') else False
            if cancel_at_period_end:
                result = self.stripe.Subscription.modify(
                    subscription['id'],
                    cancel_at_period_end = True,
                )
            else:
                results = self.stripe.Subscription.delete(subscription['id'])
        return redirect(self.success_url)

