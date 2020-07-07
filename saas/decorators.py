from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url
from django.utils.decorators import method_decorator
from functools import wraps
from saas.subscription import Customer

def subscription_required(upgrade_url=None, include_trial=True):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            resolved_upgrade_url = resolve_url(upgrade_url or settings.SAAS_UPGRADE_URL)
            if not request.user.is_authenticated:
                return HttpResponseRedirect(resolved_upgrade_url)
            customer = Customer.of(request.user)
            # If subscribed or not ignoring trial and within trial then execute view
            if customer.subscribed or (include_trial and customer.trialing):
                return view_func(request, *args, **kwargs)
            # Otherwise redirect to upgrade_url
            return HttpResponseRedirect(resolved_upgrade_url)
        return _wrapped_view
    return decorator
        