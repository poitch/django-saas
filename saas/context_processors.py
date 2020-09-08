from django.conf import settings
from saas.subscription import Customer

def referer(request):
    ref = request.GET.get('ref', None)
    if ref is not None:
        return ref
    if 'referer' in request.headers:
        return request.headers['referer']
    return None


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
    else:
        if request.session.get('referer', None) is None:
            request.session['referer'] = referer(request)
        if request.session.get('campaign', None) is None:
            request.session['campaign'] = request.GET.get('pk_campaign', None)
            request.session['content'] = request.GET.get('pk_content', None)

    return context
