import dateutil.tz as tz
import json
import uuid

from datetime import datetime
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import make_aware

User = get_user_model()

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    created_at = models.DateTimeField(
        auto_now_add=True, editable=False, db_index=True)
    modified_at = models.DateTimeField(auto_now=True, editable=False)

    @property
    def short_id(self):
        return str(self.id)[:8]

    class Meta:
        abstract = True

class StripeInfo(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    customer_id = models.CharField(max_length=256)
    subscription_id = models.CharField(max_length=512, blank=True, null=True)
    subscription_end = models.DateTimeField(blank=True, null=True)
    plan_id = models.CharField(max_length=512, blank=True, null=True, default=None)
    previously_subscribed = models.BooleanField(default=False)

    @classmethod
    def sync_with_customer(cls, customer):
        subscription = None
        if 'subscriptions' in customer and len(customer['subscriptions']['data']) > 0:
            subscription = customer['subscriptions']['data'][0]

        try:
            info = StripeInfo.objects.get(customer_id=customer['id'])
            # Update subscription info just in case!
            info.previously_subscribed = info.previously_subscribed or info.subscription_id is not None
            if subscription is not None:
                info.subscription_id = subscription['id']
                info.subscription_end = make_aware(datetime.fromtimestamp(int(subscription['current_period_end'])))
                info.plan_id = subscription['plan']['id']
            else:
                info.subscription_end = None
                info.subscription_end = None
                info.plan_id = None
            info.save()
        except StripeInfo.DoesNotExist:
            # No StripeInfo for this customer_id yet, lookup user by corresponding email.
            try:
                user = User.objects.get(email=customer['email'])
                # In case SAAS_USE_CHECKOUT settings was flipped, checked whether info already exists.
                try:
                    info = user.stripeinfo
                    # Looks like we already had a customer created for this email, so overwrite with most recent info
                    info.customer_id = customer['id']
                    info.previously_subscribed = info.previously_subscribed or info.subscription_id is not None
                    if subscription is not None:
                        info.subscription_id = subscription['id']
                        info.subscription_end = make_aware(datetime.fromtimestamp(int(subscription['current_period_end'])))
                        info.plan_id = subscription['plan']['id']
                    else:
                        info.subscription_id = None
                        info.subscription_end = None
                        info.plan_id = None
                    info.save()
                except User.stripeinfo.RelatedObjectDoesNotExist:
                    # Brand new customer, create a StripeInfo with what we need
                    info = StripeInfo.objects.create(
                        user=user,
                        customer_id=customer['id'],
                        subscription_id = subscription['id'] if subscription is not None else None,
                        subscription_end = make_aware(datetime.fromtimestamp(
                            int(subscription['current_period_end']))) if subscription is not None else None,
                        plan_id = subscription['plan']['id'] if subscription is not None else None,
                    )
            except User.DoesNotExist:
                # Could not find a user with this email, this could happen in development mode
                pass


    class Meta:
        verbose_name_plural = "Customers"


class Acquisition(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    agent = models.CharField(max_length=1024, default=None, blank=True, null=True)
    referer = models.CharField(max_length=1024, default=None, blank=True, null=True)
    campaign = models.CharField(max_length=1024, default=None, blank=True, null=True)
    content = models.CharField(max_length=1024, default=None, blank=True, null=True)


class BillingEvent(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    success = models.BooleanField(default=True)
    stripe_object = models.TextField()

    @property
    def stripe(self):
        if isinstance(self.stripe_object, str):
            return json.loads(self.stripe_object)
        return self.stripe_object

    @property
    def invoice(self):
        return self.stripe['id']

    @property
    def date(self):
        tzinfo = tz.gettz("America/Los_Angeles")
        return datetime.fromtimestamp(int(self.stripe['created']), tzinfo)

    @property
    def description(self):
        return self.stripe['lines']['data'][0]['description']

    @property
    def currency(self):
        return self.stripe['lines']['data'][0]['currency']

    @property
    def amount_due(self):
        return self.stripe['amount_due']

    @property
    def amount_paid(self):
        return self.stripe['amount_paid']


    class Meta:
        verbose_name_plural = "Bills"


class StripeEvent(BaseModel):
    event = models.CharField(max_length=256)
    object = models.TextField()
    event_id = models.CharField(max_length=256, null=True, blank=True, default=None)
    object_id = models.CharField(max_length=256, null=True, blank=True, default=None)

    class Meta:
        verbose_name_plural = "Events"

