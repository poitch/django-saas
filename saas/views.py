import logging
import stripe
import warnings

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
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View, TemplateView
from django.views.generic.edit import FormView
from saas.forms import CreateUserForm
from saas.mailer import send_multi_mail
from saas.models import StripeInfo, BillingEvent, StripeEvent, Acquisition
from saas.subscription import Customer

User = get_user_model()

if hasattr(settings, 'STRIPE_SECRET_KEY'):
    stripe.api_key = settings.STRIPE_SECRET_KEY
else:
    warnings.warn('''
        In order for django-saas to function properly, you need to set STRIPE_SECRET_KEY in settings.py
    ''')


logger = logging.getLogger("saas")


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
        user = form.save(**opts)

        # acquisition information
        Acquisition.objects.create(
            user = user,
            agent = self.request.headers['User-Agent'],
            referer = self.request.session.get('referer', None),
            campaign = self.request.session.get('campaign', None),
            content = self.request.session.get('content', None),
        )

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


class SubscribeView(LoginRequiredMixin, View):
    template_name = 'subscription/subscribe.html'
    success_url = reverse_lazy('index')

    def get(self, request, *args, **kwargs):
        plans = stripe.Plan.list()
        context = {}
        context['plans'] = plans
        context['STRIPE_PUBLISHABLE_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        token = request.POST.get('stripeToken', None)
        info = request.user.stripeinfo
        # Set default payment method
        customer = stripe.Customer.modify(
            info.customer_id,
            source=token,
        )
        # Subscribe Customer
        subscription = stripe.Subscription.create(
            customer=info.customer_id,
            trial_from_plan=True,
            items=[
                {
                    "plan": request.POST.get('plan'),
                }
            ],
            expand=['latest_invoice.payment_intent'],
        )
        # Update subscription information
        info.subscription_id = subscription['id']
        info.subscription_end = datetime.fromtimestamp(
            int(subscription['current_period_end']))
        info.save()

        return redirect(self.success_url)


class StripePortalView(View):
    return_url = reverse_lazy('index')
    def get(self, request, *args, **kwargs):
        info = request.user.stripeinfo
        url = '{}://{}{}'.format(request.scheme, request.META['HTTP_HOST'], self.return_url)
        session = stripe.billing_portal.Session.create(
            customer= info.customer_id,
            return_url=url,
        )
        print(session)
        return redirect(session['url'])

# Checkout Sequence
#   charge.succeeded
#   checkout.session.completed ()
#   payment_method.attached
#   customer.created
#   customer.subscription.created
#   invoice.created
#   invoice.updated
#   customer.subscription.updated
#   payment_intent.succeeded
#   invoice.finalized
#   customer.updated
#   invoice.updated
#   payment_intent.created
#   invoice.payment_succeeded
#   invoice.paid

class StripeWebhook(View):
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
    # Trial Will End
    trial_will_end_email_template_name = None
    trial_will_end_subject_template_name = None
    html_trial_will_end_email_template_name = None

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super(StripeWebhook, self).dispatch(request, *args, **kwargs)

    def customer_user_info(self, stripe_object):
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

        return customer_id, user, info

    def handle_stripe_event(self, request, event, stripe_object):
        if event['type'] == 'customer.created' or event['type'] == 'customer.updated':
            # This event could happen when using CHECKOUT as customers are created automatically.
            # Or when subscription is cancelled through Portal.
            StripeInfo.sync_with_customer(stripe_object)
        elif event['type'] == 'customer.subscription.deleted':
            _, _, info = self.customer_user_info(stripe_object)
            if info is not None:
                info.previously_subscribed = True
                info.subscription_id = None
                info.subscription_end = None
                info.plan_id = None
                info.save()
        elif event['type'] == 'invoice.payment_succeeded':
            _, user, _ = self.customer_user_info(stripe_object)
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
            _, user, _ = self.customer_user_info(stripe_object)
            if user is not None:
                billing = BillingEvent.objects.create(
                    user=user,
                    success=False,
                    stripe_object=stripe_object,
                )
                self.on_payment_failed(request, user, billing, stripe_object)
        elif event['type'] == 'invoice.payment_action_required':
            _, user, _ = self.customer_user_info(stripe_object)
            if user is not None:
                self.on_payment_action_required(request, user, stripe_object)
        elif event['type'] == 'invoice.upcoming':
            _, user, _ = self.customer_user_info(stripe_object)
            if user is not None:
                self.on_invoice_incoming(request, user, stripe_object)
        elif event['type'] == 'customer.subscription.updated':
            _, _, info = self.customer_user_info(stripe_object)
            if info is not None:
                info.subscription_id = stripe_object['id']
                info.subscription_end = make_aware(datetime.fromtimestamp(int(stripe_object['current_period_end'])))
                info.plan_id = stripe_object['plan']['id']
                info.save()
        elif event['type'] == 'customer.subscription.trial_will_end':
            _, user, _ = self.customer_user_info(stripe_object)
            if user is not None:
                self.on_trial_will_end(request, user, stripe_object)
        elif event['type'] == 'customer.subscription.created':
            _, _, info = self.customer_user_info(stripe_object)
            if info is not None:
                info.subscription_id = stripe_object['id']
                info.subscription_end = make_aware(datetime.fromtimestamp(int(stripe_object['current_period_end'])))
                info.plan_id = stripe_object['plan']['id']
                info.save()

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
            logger.warn(f'ValueError {e}')
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            logger.warn(f'SignatureVerificationError {e}')
            return HttpResponse(status=400)

        stripe_object = event['data']['object']

        # Record Event
        StripeEvent.objects.create(
            event=event['type'],
            object=stripe_object,
        )

        self.handle_stripe_event(request, event, stripe_object)

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
            'invoice': stripe_object,
            'protocol': request.scheme,
            'domain': request.META['HTTP_HOST'],
        }
        send_multi_mail(self.invoice_incoming_subject_template_name, self.invoice_incoming_email_template_name, context,
                        self.from_email, user.email, html_email_template_name=self.html_invoice_incoming_email_template_name)

    def on_trial_will_end(self, request, user, stripe_object):
        if self.trial_will_end_email_template_name is None or self.trial_will_end_subject_template_name is None:
            return
        context = {
            'request': request,
            'user': user,
            'trial': stripe_object,
            'protocol': request.scheme,
            'domain': request.META['HTTP_HOST'],
        }
        send_multi_mail(self.trial_will_end_subject_template_name, self.trial_will_end_email_template_name, context,
                        self.from_email, user.email, html_email_template_name=self.html_trial_will_end_email_template_name)

class BillingView(View):
    template_name = 'subscription/billing.html'

    def get(self, request, billing_id):
        billing = get_object_or_404(BillingEvent, pk=billing_id)
        if billing.user != request.user:
            raise Http404

        context = {}
        context['billing'] = billing

        return render(request, self.template_name, context)


class UpdatePaymentView(LoginRequiredMixin, View):
    template_name = 'subscription/update_payment.html'
    success_url = reverse_lazy('index')

    def get(self, request, *args, **kwargs):
        context = {}
        context['STRIPE_PUBLISHABLE_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        info = request.user.stripeinfo
        customer = stripe.Customer.modify(
            info.customer_id,
            source=request.POST.get('stripeToken')
        )
        stripe.Subscription.modify(
            info.subscription_id,
            default_source=customer['sources']['data'][0]['id'],
        )
        return redirect(self.success_url)

class UpdatePlanView(LoginRequiredMixin, View):
    template_name = 'subscription/update_plan.html'
    success_url = reverse_lazy('index')

    def get(self, request, *args, **kwargs):
        context = {}
        context['STRIPE_PUBLISHABLE_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        info = request.user.stripeinfo
        stripe.Subscription.modify(
            info.subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "plan": request.POST.get('plan'),
                }
            ],
            expand=['latest_invoice.payment_intent'],
        )

class SubscriptionView(LoginRequiredMixin, TemplateView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        info = self.request.user.stripeinfo
        customer = stripe.Customer.retrieve(info.customer_id)
        card = None
        subscription = None
        if len(customer['sources']['data']) > 0:
            card = customer['sources']['data'][0]
        if len(customer['subscriptions']['data']) > 0:
            subscription = customer['subscriptions']['data'][0]
        for billing in BillingEvent.objects.filter(user=self.request.user).order_by('-created_at'):
            context['billing'].append(billing)

        context['customer'] = customer
        context['card'] = card
        context['subscription'] = subscription
        return context

class CancelSubscriptionView(LoginRequiredMixin, View):
    success_url = reverse_lazy('index')

    def get(self, request):
        info = request.user.stripeinfo
        if info.subscription_id is not None:
            cancel_at_period_end = settings.SAAS_CANCEL_SUBSCRIPTION_AT_PERIOD_END if hasattr(settings, 'SAAS_CANCEL_SUBSCRIPTION_AT_PERIOD_END') else False
            if cancel_at_period_end:
                _ = stripe.Subscription.modify(
                    info.subscription_id,
                    cancel_at_period_end = True,
                )
            else:
                _ = stripe.Subscription.delete(info.subscription_id)
        return redirect(self.success_url)

