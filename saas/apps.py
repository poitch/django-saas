from django.apps import AppConfig
from django.conf import settings


class SaasConfig(AppConfig):
    name = 'saas'

    def ready(self):
        import saas.signals
        if not hasattr(settings, 'STRIPE_API_KEY'):
            print('In order for django-saas to function properly, you need to set STRIPE_API_KEY in settings.py')
        stripe.api_key = settings.STRIPE_API_KEY
