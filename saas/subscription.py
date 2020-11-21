import stripe

from datetime import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from saas.models import StripeInfo

User = get_user_model()

class Customer:
    def __init__(self, user):
        super().__init__()
        self._user = user

    def __str__(self):
        part1 = 'Subscribed' if self.actively_subscribed else ''
        part2 = 'Trialing' if self.trialing else ''

    @classmethod
    def of(cls, user):
        return Customer(user)

    @property
    def info(self):
        try:
            return self._user.stripeinfo
        except User.stripeinfo.RelatedObjectDoesNotExist:
            return None

    @property
    def subscribed(self):
        return self.trialing or self.actively_subscribed

    @property
    def actively_subscribed(self):
        info = self.info
        if info is None:
            return False
        return self._user.is_staff or (info.subscription_end is not None and timezone.now() <= info.subscription_end)

    @property
    def previously_subscribed(self):
        info = self.info
        if info is None:
            return False
        return info.previously_subscribed

    @property
    def trial_duration_in_seconds(self):
        days = settings.SAAS_TRIAL_DAYS if hasattr(settings, 'SAAS_TRIAL_DAYS') else 30
        return (1 + days) * 24 * 3600

    @property
    def trialing(self):
        if self.actively_subscribed:
            return False
        if self.previously_subscribed:
            return False
        enable_trial = settings.SAAS_ENABLE_TRIAL if hasattr(settings, 'SAAS_ENABLE_TRIAL') else True
        if not enable_trial:
            return False
        delta = timezone.now() - self._user.date_joined
        return delta.total_seconds() < self.trial_duration_in_seconds

    @property
    def trial_left_in_seconds(self):
        return self.trial_duration_in_seconds - (timezone.now() - self._user.date_joined).total_seconds()

    @property
    def trial_left_in_days(self):
        return int((self.trial_duration_in_seconds - (timezone.now() - self._user.date_joined).total_seconds()) // (24 * 3600))

