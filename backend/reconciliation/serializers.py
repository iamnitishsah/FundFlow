from rest_framework import serializers
from .models import (
    Organization,
    CapitalCall,
    InvestorEntity,
    LineItem,
    BankTransaction,
    MatchProposal,
)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "slug", "name"]


class InvestorEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestorEntity
        fields = ["id", "name", "normalized_name"]


class CapitalCallSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapitalCall
        fields = ["id", "call_number", "call_date", "due_date"]


class LineItemSerializer(serializers.ModelSerializer):
    investor_name = serializers.CharField(
        source="investor_entity.name",
        read_only=True,
    )
    call_number = serializers.IntegerField(
        source="capital_call.call_number",
        read_only=True,
    )
    call_date = serializers.DateField(
        source="capital_call.call_date",
        read_only=True,
    )
    amount_remaining = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = LineItem
        fields = [
            "id",
            "wire_reference",
            "normalized_reference",
            "amount_called",
            "amount_funded",
            "amount_remaining",
            "status",
            "investor_name",
            "call_number",
            "call_date",
        ]


class MatchProposalSerializer(serializers.ModelSerializer):
    line_item_reference = serializers.CharField(
        source="line_item.wire_reference",
        read_only=True,
    )
    investor_name = serializers.CharField(
        source="line_item.investor_entity.name",
        read_only=True,
    )
    line_item_remaining = serializers.DecimalField(
        source="line_item.amount_remaining",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = MatchProposal
        fields = [
            "id",
            "line_item",
            "line_item_reference",
            "investor_name",
            "line_item_remaining",
            "match_status",
            "reason",
            "created_at",
        ]


class BankTransactionSerializer(serializers.ModelSerializer):
    matches = MatchProposalSerializer(many=True, read_only=True)
    suggested_match = serializers.SerializerMethodField()

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "date",
            "description",
            "amount",
            "type",
            "bank_reference",
            "status",
            "needs_review_reason",
            "raw_file_line",
            "matches",
            "suggested_match",
        ]

    def get_suggested_match(self, obj):
        proposed = [m for m in obj.matches.all() if m.match_status == MatchProposal.STATUS_PROPOSED]
        if proposed:
            return MatchProposalSerializer(proposed[0]).data
        approved = [m for m in obj.matches.all() if m.match_status == MatchProposal.STATUS_APPROVED]
        if approved:
            return MatchProposalSerializer(approved[0]).data
        return None


class CsvUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

