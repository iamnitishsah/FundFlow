from django.contrib import admin
from .models import (
    Organization,
    CapitalCall,
    InvestorEntity,
    LineItem,
    BankTransaction,
    MatchProposal,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")


@admin.register(CapitalCall)
class CapitalCallAdmin(admin.ModelAdmin):
    list_display = ("organization", "call_number", "call_date", "due_date")
    list_filter = ("organization",)
    search_fields = ("organization__name", "call_number")


@admin.register(InvestorEntity)
class InvestorEntityAdmin(admin.ModelAdmin):
    list_display = ("name", "normalized_name", "organization")
    list_filter = ("organization",)
    search_fields = ("name", "normalized_name")


@admin.register(LineItem)
class LineItemAdmin(admin.ModelAdmin):
    list_display = (
        "wire_reference",
        "investor_entity",
        "capital_call",
        "amount_called",
        "amount_funded",
        "status",
    )
    list_filter = ("status", "capital_call__organization")
    search_fields = ("wire_reference", "normalized_reference", "investor_entity__name")


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "bank_reference",
        "organization",
        "amount",
        "type",
        "status",
    )
    list_filter = ("organization", "type", "status")
    search_fields = ("bank_reference", "description")


@admin.register(MatchProposal)
class MatchProposalAdmin(admin.ModelAdmin):
    list_display = ("transaction", "line_item", "match_status", "created_at")
    list_filter = ("match_status",)
    search_fields = (
        "transaction__bank_reference",
        "line_item__wire_reference",
        "reason",
    )
