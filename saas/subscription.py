import pytz

from datetime import datetime
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
        info = self._user.stripeinfo
        if not info:
            return False
        utc = pytz.UTC 
        return self._user.is_staff or (info.subscription_end is not None and datetime.now().replace(tzinfo=utc) <= info.subscription_end.replace(tzinfo=utc))
