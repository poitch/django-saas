from saas.subscription import Customer

def current_customer(request):
    if request.user.is_authenticated:
        return {'customer': Customer.of(request.user)}
    return {'customer': None}
