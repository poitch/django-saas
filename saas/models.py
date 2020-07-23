import uuid

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)
    created_at = models.DateTimeField(
        auto_now_add=True, editable=False, db_index=True)
    modified_at = models.DateTimeField(auto_now=True, editable=False)

    @property
    def short_id(self):
        return str(self.id)[:8]

    class Meta:
        abstract = True

class StripeInfo(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    customer_id = models.CharField(max_length=256)
    subscription_id = models.CharField(max_length=512, blank=True, null=True)
    subscription_end = models.DateTimeField(blank=True, null=True)
    class Meta:
        verbose_name_plural = "Customers"

class BillingEvent(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    success = models.BooleanField(default=True)
    stripe_object = models.TextField()
    class Meta:
        verbose_name_plural = "Bills"


class StripeEvent(BaseModel):
    event = models.CharField(max_length=256)
    object = models.TextField()
    class Meta:
        verbose_name_plural = "Events"

