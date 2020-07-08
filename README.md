# django-saas
 
django-saas is a Django application that provides the common functionality found in SaaS projects. As such, it provides 2-step registration and a subscription management mechanism.

The subscription management system relies on Stripe. It handles trial periods and the lifecycle of the subscription by implementing all of the boilerplate code to handle the messages received from Stripe.

This application also generates corresponding emails and thanks to the modularity of Django allows for complete customization of the screens and emails.
