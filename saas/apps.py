from django.apps import AppConfig
from django.conf import settings


class SaasConfig(AppConfig):
    name = 'saas'

    def ready(self):
        import saas.signals
        if not hasattr(settings, 'STRIPE_SECRET_KEY'):
            print('In order for django-saas to function properly, you need to set STRIPE_SECRET_KEY in settings.py')
        if hasattr(settings, 'SAAS_USE_CHECKOUT') and settings.SAAS_USE_CHECKOUT and not hasattr(settings, 'SAAS_CHECKOUT_PRICE_ID'):
            print('SAAS_USE_CHECKOUT is enabled but SAAS_CHECKOUT_PRICE_ID is not defined')
