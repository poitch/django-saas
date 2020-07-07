import pytz

from datetime import datetime
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

class Customer:
    def __init__(self, user):
        super().__init__()
        self._user = user
    
    @classmethod
    def of(cls, user):
        return Customer(user)

    @property
    def subscribed(self):
        try:
            info = self._user.stripeinfo
            utc = pytz.UTC 
            return self._user.is_staff or (info.subscription_end is not None and datetime.now().replace(tzinfo=utc) <= info.subscription_end.replace(tzinfo=utc))
        except User.stripeinfo.RelatedObjectDoesNotExist:
            return False

    @property
    def trial_duration_in_seconds(self):
        days = settings.SAAS_TRIAL_DAYS if hasattr(settings, 'SAAS_TRIAL_DAYS') else 30
        return days * 24 * 3600

    @property
    def trialing(self):
        if self.subscribed:
            return False
        enable_trial = settings.SAAS_ENABLE_TRIAL if hasattr(settings, 'SAAS_ENABLE_TRIAL') else True
        if not settings.SAAS_ENABLE_TRIAL:
            return False
        delta = datetime.now() - self._user.date_joined
        return delta.total_seconds() < self.trial_duration_in_seconds
    
    @property
    def trial_left_in_seconds(self):
        return self.trial_duration_in_seconds - (datetime.now() - self._user.date_joined).total_seconds()

    @property
    def trial_left_in_days(self):
        return int((self.trial_duration_in_seconds - (datetime.now() - self._user.date_joined).total_seconds()) // (24 * 3600))
