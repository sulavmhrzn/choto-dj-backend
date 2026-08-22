from django.contrib import admin

from apps.billing.models import (
    BillingCustomer,
    Plan,
    ProviderPlanPrice,
    ProviderSubscription,
    Subscription,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin): ...


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin): ...


@admin.register(BillingCustomer)
class BillingCustomerAdmin(admin.ModelAdmin): ...


@admin.register(ProviderSubscription)
class ProviderSubscriptionAdmin(admin.ModelAdmin): ...


@admin.register(ProviderPlanPrice)
class ProviderPlanPriceAdmin(admin.ModelAdmin): ...
