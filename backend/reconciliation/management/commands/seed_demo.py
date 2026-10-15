from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from reconciliation.models import (
    Organization,
    CapitalCall,
    InvestorEntity,
    LineItem,
)


class Command(BaseCommand):
    help = "Seed demo organizations, capital calls, and line items."

    @transaction.atomic
    def handle(self, *args, **options):
        org_data = [
            ("northwind", "Northwind Ventures"),
            ("bluebird", "Bluebird Capital"),
        ]

        orgs = {}
        for slug, name in org_data:
            org, _ = Organization.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
            orgs[slug] = org

        calls_data = [
            ("northwind", 1, date(2026, 3, 25), date(2026, 4, 10)),
            ("northwind", 2, date(2026, 4, 1), date(2026, 4, 20)),
            ("bluebird", 1, date(2026, 4, 1), date(2026, 4, 15)),
        ]

        calls = {}
        for org_slug, call_num, call_date, due_date in calls_data:
            call, _ = CapitalCall.objects.get_or_create(
                organization=orgs[org_slug],
                call_number=call_num,
                defaults={
                    "call_date": call_date,
                    "due_date": due_date,
                },
            )
            calls[(org_slug, call_num)] = call

        line_items_data = [
            (
                "northwind",
                1,
                "Haller Capital LLC",
                "CC-1001",
                Decimal("27500.00"),
            ),
            (
                "northwind",
                1,
                "Rahul Shah Trust",
                "CC-1002",
                Decimal("25000.00"),
            ),
            (
                "northwind",
                1,
                "Patel Family Trust",
                "CC-1003",
                Decimal("12500.00"),
            ),
            (
                "northwind",
                1,
                "Meridian Partners LP",
                "CC-1004",
                Decimal("15000.00"),
            ),
            (
                "northwind",
                1,
                "Oakridge Holdings LLC",
                "CC-1005",
                Decimal("15000.00"),
            ),
            (
                "northwind",
                2,
                "Oakridge Holdings LLC",
                "CC-1006",
                Decimal("15000.00"),
            ),
            (
                "bluebird",
                1,
                "Cedar Grove Fund LP",
                "CC-2001",
                Decimal("40000.00"),
            ),
        ]

        for org_slug, call_num, investor_name, ref, amount in line_items_data:
            org = orgs[org_slug]
            call = calls[(org_slug, call_num)]
            investor, _ = InvestorEntity.objects.get_or_create(
                organization=org,
                name=investor_name,
            )
            LineItem.objects.get_or_create(
                capital_call=call,
                wire_reference=ref,
                defaults={
                    "investor_entity": investor,
                    "amount_called": amount,
                    "amount_funded": Decimal("0.00"),
                    "status": LineItem.STATUS_OPEN,
                },
            )

        self.stdout.write(
            self.style.SUCCESS("Successfully seeded demo data for northwind and bluebird.")
        )

