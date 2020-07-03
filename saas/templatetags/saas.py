
import currency
from datetime import datetime
from django import template

register = template.Library()

@register.filter
def stripe_amount(amount, symbol):
    return currency.pretty(amount / pow(10, currency.decimals(symbol)), symbol)

@register.filter(name='fromunix')
def fromunix(value):
    return datetime.fromtimestamp(int(value))
