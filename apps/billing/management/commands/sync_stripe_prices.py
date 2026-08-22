from django.core.management.base import BaseCommand, CommandError

from apps.billing.models import PaymentProvider, Plan, PlanCode, ProviderPlanPrice


class Command(BaseCommand):
    help = "Create or update the ProviderPlanPrice mapping for a plan"

    def add_arguments(self, parser):
        parser.add_argument("plan_code", type=str)
        parser.add_argument("provider_price_id", type=str)

    def handle(self, *args, **options):
        plan_code = options["plan_code"]
        provider_price_id = options["provider_price_id"]

        if plan_code not in PlanCode.values:
            raise CommandError(f"Unknown plan code: {plan_code}")

        plan = Plan.objects.get(code=plan_code)

        provider_plan_price, created = ProviderPlanPrice.objects.update_or_create(
            plan=plan,
            provider=PaymentProvider.STRIPE,
            defaults={"provider_price_id": provider_price_id},
        )

        action = "Created" if created else "Updated"

        self.stdout.write(
            self.style.SUCCESS(
                f"{action} price mapping: {plan.code} -> {provider_price_id}"
            )
        )
