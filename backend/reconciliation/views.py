from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import (
    Organization,
    LineItem,
    BankTransaction,
)
from .tenant import TenantScopedMixin
from .serializers import (
    OrganizationSerializer,
    LineItemSerializer,
    BankTransactionSerializer,
    MatchProposalSerializer,
)
from .services.csv_importer import CsvImportService
from .services.reconciliation_service import ReconciliationService


class OrganizationListView(generics.ListAPIView):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer


class LineItemListView(TenantScopedMixin, generics.ListAPIView):
    serializer_class = LineItemSerializer
    queryset = LineItem.objects.select_related(
        "capital_call",
        "investor_entity",
    ).all()
    ordering = ["capital_call__call_number", "wire_reference"]


class BankTransactionListView(TenantScopedMixin, generics.ListAPIView):
    serializer_class = BankTransactionSerializer
    queryset = BankTransaction.objects.prefetch_related(
        "matches__line_item__investor_entity",
    ).all()
    ordering = ["-date", "-created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class StatementUploadView(TenantScopedMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response(
                {"detail": "No file was uploaded under the 'file' parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = CsvImportService(self.organization)
        summary = service.parse_and_import(uploaded_file)

        created_txns = summary.pop("created_transactions", [])
        summary["transactions"] = BankTransactionSerializer(
            created_txns,
            many=True,
        ).data

        return Response(summary, status=status.HTTP_200_OK)


class ApproveMatchView(TenantScopedMixin, APIView):
    def post(self, request, match_id):
        service = ReconciliationService(self.organization)
        match = service.approve_match(match_id)
        return Response(
            MatchProposalSerializer(match).data,
            status=status.HTTP_200_OK,
        )


class RejectMatchView(TenantScopedMixin, APIView):
    def post(self, request, match_id):
        service = ReconciliationService(self.organization)
        match = service.reject_match(match_id)
        return Response(
            MatchProposalSerializer(match).data,
            status=status.HTTP_200_OK,
        )


class IgnoreTransactionView(TenantScopedMixin, APIView):
    def post(self, request, transaction_id):
        service = ReconciliationService(self.organization)
        txn = service.ignore_transaction(transaction_id)
        return Response(
            BankTransactionSerializer(txn).data,
            status=status.HTTP_200_OK,
        )
