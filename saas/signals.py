import logging
import stripe

from datetime import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import make_aware
from saas.models import StripeInfo

User = get_user_model()

logger = logging.getLogger("saas")

@receiver(post_save, sender=User)
def on_new_user(sender, instance, created, **kwargs):
    if created:
        # Do not create a customer when using CHECKOUT
        if hasattr(settings, 'SAAS_USE_CHECKOUT') and settings.SAAS_USE_CHECKOUT:
            return
        # Create a Stripe Customer and store customer id
        customer = None
        subscription = None
        if settings.DEBUG:
            # When in DEBUG mode, check if email is already
            # registered with Stripe. This can happen when wiping local database
            # but not cleaning up database in production.
            results = stripe.Customer.list(
                email=instance.email,
            )
            for result in results['data']:
                if 'deleted' not in result:
                    customer = result
                    # Re-attach subscription if there was one.
                    if len(customer['subscriptions']['data']) > 0:
                        subscription = customer['subscriptions']['data'][0]
                    break

        if customer is None:
            # 2) No existing customer found, create a new one.
            customer = stripe.Customer.create(
                email=instance.email,
            )

        logger.info('Created Stripe Customer {}'.format(customer['id']))
        StripeInfo.objects.create(
            user=instance,
            customer_id=customer['id'],
            subscription_id = subscription['id'] if subscription is not None else None,
            subscription_end = datetime.fromtimestamp(
                int(subscription['current_period_end'])) if subscription is not None else None,
        )

@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    customer = None
    info = None
    try:
        info = user.stripeinfo
        try:
            customer = stripe.Customer.retrieve(info.customer_id, expand=['subscriptions'])
            print(customer)
            if 'deleted' in customer:
                info.delete()
                return
        except stripe.error.InvalidRequestError:
            return
    except User.stripeinfo.RelatedObjectDoesNotExist:
        return

    subscription = None
    if 'subscriptions' in customer and len(customer['subscriptions']['data']) > 0:
        subscription = customer['subscriptions']['data'][0]
    if subscription is not None:
        print('subscription = {}'.format(subscription))
        info.previously_subscribed = info.previously_subscribed or (info.subscription_id is not None and subscription.id != info.subscription_id)
        info.subscription_id = subscription['id']
        info.subscription_end = make_aware(datetime.fromtimestamp(int(subscription['current_period_end'])))
        info.plan_id = subscription['plan']['id']
        info.save()
