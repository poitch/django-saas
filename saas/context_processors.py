from django.conf import settings
from saas.subscription import Customer

def current_customer(request):
    context = {
        'customer': None,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY,
    }
    if hasattr(settings, 'SAAS_USE_CHECKOUT') and settings.SAAS_USE_CHECKOUT:
        if hasattr(settings, 'SAAS_CHECKOUT_PRICE_ID'):
            context['SAAS_CHECKOUT_PRICE_ID'] = settings.SAAS_CHECKOUT_PRICE_ID
    if request.user.is_authenticated:
        context['customer'] = Customer.of(request.user)
    
    return context
