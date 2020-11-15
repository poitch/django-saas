# django-saas
 
django-saas is a Django application that provides the common functionality found in SaaS projects. As such, it provides 2-step registration and a subscription management mechanism.

The subscription management system relies on Stripe. It handles trial periods and the lifecycle of the subscription by implementing all of the boilerplate code to handle the messages received from Stripe.

This application also generates corresponding emails and thanks to the modularity of Django allows for complete customization of the screens and emails.

## Setup

First add the `saas` application to the list of installed applications. `saas` depends on `captcha` for the registration, so you will need to add both applications.

```python
INSTALLED_APPS = [
    ...
    'saas',
    'captcha',
    ...
]
```

Next you will need to install a `context_processors` so that `customer` is defined in your template's context.

```python
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            'context_processors': [
                ...
                'saas.context_processors.current_customer',
            ]
        }
    }
]
```

Finally, you will need to define a few constants to configure `RECAPTCHA` and `STRIPE`
```python
### RECAPTCHA
RECAPTCHA_PRIVATE_KEY = os.getenv('RECAPTCHA_PRIVATE_KEY')
RECAPTCHA_PUBLIC_KEY = os.getenv('RECAPTCHA_PUBLIC_KEY')

# STRIPE
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_ENDPOINT_SECRET = os.getenv('STRIPE_ENDPOINT_SECRET')
```

## Configuration

`django-saas`'s behavior is controlled through a few settings constants. 

```python
SAAS_UPGRADE_URL = '/upgrade'
SAAS_ENABLE_TRIAL = True
SAAS_TRIAL_DAYS = 30
SAAS_CANCEL_SUBSCRIPTION_AT_PERIOD_END = False
SAAS_USE_CHECKOUT = True
SAAS_CHECKOUT_PRICE_ID = os.getenv('SAAS_CHECKOUT_PRICE_ID')
```

`SAAS_ENABLE_TRIAL` is used to control whether the application handles the trial on its own. If `True` then `django-saas` will keep track of when people registered and compute where they are at in their trial. You can control the trial duration through `SAAS_TRIAL_DAYS`. If set to `False`, then `django-saas` will rely on Stripe for the trial.

`SAAS_USE_CHECKOUT` controls whether `django-saas` will rely on Stripe Checkout for subscriptions. If not then you can use the built-in views to handle a custom checkout process.

When `SAAS_USE_CHECKOUT` is set to `True` you need to provide `SAAS_CHECKOUT_PRICE_ID` for the redirect properly.
