import io
import os
from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from .models import (
    Organization,
    CapitalCall,
    InvestorEntity,
    LineItem,
    BankTransaction,
    MatchProposal,
)
from .tenant import (
    get_tenant_organization,
    MissingOrganizationHeader,
    OrganizationNotFound,
    TenantScopedMixin,
)
from .services.csv_importer import (
    CsvImportService,
    MissingCsvColumnError,
)
from .services.matching_engine import (
    MatchingEngineService,
    normalize_reference,
    normalize_investor_name,
    is_name_in_description,
)
from .services.reconciliation_service import (
    ReconciliationService,
    ReconciliationConflictError,
)


class DummyScopedView(TenantScopedMixin, APIView):
    def get(self, request):
        return Response({"organization": self.organization.slug})


class DummyLineItemListView(TenantScopedMixin, generics.GenericAPIView):
    queryset = LineItem.objects.all()

    def get(self, request):
        qs = self.get_queryset()
        return Response([item.wire_reference for item in qs])


class AssessmentSpecificationRequiredTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org_northwind = Organization.objects.create(
            slug="northwind",
            name="Northwind Ventures",
        )
        self.org_bluebird = Organization.objects.create(
            slug="bluebird",
            name="Bluebird Capital",
        )

        self.call1 = CapitalCall.objects.create(
            organization=self.org_northwind,
            call_number=1,
            call_date=date(2026, 3, 25),
            due_date=date(2026, 4, 10),
        )
        self.call2 = CapitalCall.objects.create(
            organization=self.org_northwind,
            call_number=2,
            call_date=date(2026, 4, 1),
            due_date=date(2026, 4, 20),
        )

        self.inv_haller = InvestorEntity.objects.create(
            organization=self.org_northwind,
            name="Haller Capital LLC",
        )
        self.inv_rahul = InvestorEntity.objects.create(
            organization=self.org_northwind,
            name="Rahul Shah Trust",
        )
        self.inv_patel = InvestorEntity.objects.create(
            organization=self.org_northwind,
            name="Patel Family Trust",
        )
        self.inv_oakridge = InvestorEntity.objects.create(
            organization=self.org_northwind,
            name="Oakridge Holdings LLC",
        )

        self.li_1001 = LineItem.objects.create(
            capital_call=self.call1,
            investor_entity=self.inv_haller,
            wire_reference="CC-1001",
            amount_called=Decimal("27500.00"),
        )
        self.li_1002 = LineItem.objects.create(
            capital_call=self.call1,
            investor_entity=self.inv_rahul,
            wire_reference="CC-1002",
            amount_called=Decimal("25000.00"),
        )
        self.li_1003 = LineItem.objects.create(
            capital_call=self.call1,
            investor_entity=self.inv_patel,
            wire_reference="CC-1003",
            amount_called=Decimal("12500.00"),
        )
        self.li_1005 = LineItem.objects.create(
            capital_call=self.call1,
            investor_entity=self.inv_oakridge,
            wire_reference="CC-1005",
            amount_called=Decimal("15000.00"),
        )
        self.li_1006 = LineItem.objects.create(
            capital_call=self.call2,
            investor_entity=self.inv_oakridge,
            wire_reference="CC-1006",
            amount_called=Decimal("15000.00"),
        )

        self.call_bb = CapitalCall.objects.create(
            organization=self.org_bluebird,
            call_number=1,
            call_date=date(2026, 4, 1),
            due_date=date(2026, 4, 15),
        )
        self.inv_bb = InvestorEntity.objects.create(
            organization=self.org_bluebird,
            name="Cedar Grove Fund LP",
        )
        self.li_2001 = LineItem.objects.create(
            capital_call=self.call_bb,
            investor_entity=self.inv_bb,
            wire_reference="CC-2001",
            amount_called=Decimal("40000.00"),
        )

        self.csv_service_nw = CsvImportService(self.org_northwind)
        self.recon_service_nw = ReconciliationService(self.org_northwind)
        self.recon_service_bb = ReconciliationService(self.org_bluebird)

    def test_req1_missing_column_rejects_file_and_saves_nothing(self):
        missing_csv = "date,description,amount,type\n2026-04-03,WIRE RAHUL SHAH,25000.00,credit\n"
        with self.assertRaises(MissingCsvColumnError):
            self.csv_service_nw.parse_and_import(missing_csv)
        self.assertEqual(BankTransaction.objects.filter(organization=self.org_northwind).count(), 0)

        file_obj = SimpleUploadedFile("statement.csv", missing_csv.encode("utf-8"), content_type="text/csv")
        response = self.client.post(
            "/api/statements/upload/",
            {"file": file_obj},
            format="multipart",
            HTTP_X_ORGANIZATION="northwind",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_req2_amount_parsing_thousands_separators_sign_mismatch_and_decimal(self):
        csv_data = (
            "date,description,amount,type,reference\n"
            '2026-04-03,VALID COMMA WIRE,"25,000.00",credit,REF_VALID\n'
            "2026-04-31,INVALID CALENDAR DATE,500.00,credit,REF_DATE\n"
            "2026-04-17,NEGATIVE CREDIT,-15000.00,credit,REF_NEG_CREDIT\n"
            "2026-04-17,POSITIVE DEBIT,100.00,debit,REF_POS_DEBIT\n"
            "2026-04-17,ZERO AMOUNT,0.00,credit,REF_ZERO\n"
        )
        result = self.csv_service_nw.parse_and_import(csv_data)
        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["error_count"], 4)

        txn = BankTransaction.objects.get(bank_reference="REF_VALID")
        self.assertIsInstance(txn.amount, Decimal)
        self.assertEqual(txn.amount, Decimal("25000.00"))

    def test_req3_duplicates_inside_file_and_reupload(self):
        csv_data = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE 1,1000.00,credit,FT_DUP_1\n"
            "2026-04-04,WIRE 2,1000.00,credit,FT_DUP_1\n"
        )
        result1 = self.csv_service_nw.parse_and_import(csv_data)
        self.assertEqual(result1["imported_count"], 1)
        self.assertEqual(result1["duplicate_count"], 1)
        self.assertEqual(result1["duplicates"][0]["line"], 3)

        result2 = self.csv_service_nw.parse_and_import(csv_data)
        self.assertEqual(result2["imported_count"], 0)
        self.assertEqual(result2["duplicate_count"], 2)

    def test_req4_reference_match_including_casing_and_partial_payment(self):
        csv_data = (
            "date,description,amount,type,reference\n"
            "2026-04-04,ACH CREDIT HALLER CAPITAL cc1001,20000.00,credit,ACH_PARTIAL_1\n"
            "2026-04-14,ACH CREDIT HALLER CAPITAL cc1001,7500.00,CREDIT,ACH_PARTIAL_2\n"
        )
        result = self.csv_service_nw.parse_and_import(csv_data)
        self.assertEqual(result["imported_count"], 2)

        txn1 = BankTransaction.objects.get(bank_reference="ACH_PARTIAL_1")
        self.assertEqual(txn1.status, BankTransaction.STATUS_SUGGESTED)
        self.assertEqual(txn1.matches.first().line_item, self.li_1001)

        txn2 = BankTransaction.objects.get(bank_reference="ACH_PARTIAL_2")
        self.assertEqual(txn2.status, BankTransaction.STATUS_SUGGESTED)
        self.assertEqual(txn2.matches.first().line_item, self.li_1001)

    def test_req5_name_and_amount_match_and_multiple_candidates(self):
        csv_single = (
            "date,description,amount,type,reference\n"
            "2026-04-07,WIRE INCOMING PATEL FAMILY TRUST,12500.00,credit,FT_PATEL\n"
        )
        self.csv_service_nw.parse_and_import(csv_single)
        txn_patel = BankTransaction.objects.get(bank_reference="FT_PATEL")
        self.assertEqual(txn_patel.status, BankTransaction.STATUS_SUGGESTED)
        self.assertEqual(txn_patel.matches.count(), 1)
        self.assertEqual(txn_patel.matches.first().line_item, self.li_1003)

        csv_multi = (
            "date,description,amount,type,reference\n"
            "2026-04-11,WIRE INCOMING OAKRIDGE HOLDINGS LLC,15000.00,credit,FT_OAKRIDGE\n"
        )
        self.csv_service_nw.parse_and_import(csv_multi)
        txn_oakridge = BankTransaction.objects.get(bank_reference="FT_OAKRIDGE")
        self.assertEqual(txn_oakridge.status, BankTransaction.STATUS_NEEDS_REVIEW)
        self.assertEqual(txn_oakridge.matches.count(), 2)
        proposed_refs = {m.line_item.wire_reference for m in txn_oakridge.matches.all()}
        self.assertEqual(proposed_refs, {"CC-1005", "CC-1006"})

    def test_req6_overpayment_becomes_needs_review_with_no_match(self):
        csv_overpay = (
            "date,description,amount,type,reference\n"
            "2026-04-15,WIRE INCOMING PATEL FAMILY TRUST CC-1003,13000.00,credit,FT_OVERPAY\n"
        )
        self.csv_service_nw.parse_and_import(csv_overpay)
        txn_overpay = BankTransaction.objects.get(bank_reference="FT_OVERPAY")
        self.assertEqual(txn_overpay.status, BankTransaction.STATUS_NEEDS_REVIEW)
        self.assertEqual(txn_overpay.matches.count(), 0)
        self.assertIn("Overpayment", txn_overpay.needs_review_reason)

    def test_req7_approving_updates_funded_and_second_approval_returns_409(self):
        csv_data = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE INCOMING RAHUL SHAH TRUST REF CC-1002,25000.00,credit,FT_RAHUL\n"
        )
        self.csv_service_nw.parse_and_import(csv_data)
        txn = BankTransaction.objects.get(bank_reference="FT_RAHUL")
        match = txn.matches.first()

        approved_match = self.recon_service_nw.approve_match(match.id)
        self.assertEqual(approved_match.match_status, MatchProposal.STATUS_APPROVED)

        self.li_1002.refresh_from_db()
        self.assertEqual(self.li_1002.amount_funded, Decimal("25000.00"))
        self.assertEqual(self.li_1002.status, LineItem.STATUS_FUNDED)

        txn.refresh_from_db()
        self.assertEqual(txn.status, BankTransaction.STATUS_RECONCILED)

        with self.assertRaises(ReconciliationConflictError) as ctx:
            self.recon_service_nw.approve_match(match.id)
        self.assertEqual(ctx.exception.status_code, status.HTTP_409_CONFLICT)

        self.li_1002.refresh_from_db()
        self.assertEqual(self.li_1002.amount_funded, Decimal("25000.00"))

    def test_req8_organization_isolation_listing_and_approving_returns_404(self):
        resp_missing = self.client.get("/api/line-items/")
        self.assertEqual(resp_missing.status_code, status.HTTP_400_BAD_REQUEST)

        resp_unknown = self.client.get("/api/line-items/", HTTP_X_ORGANIZATION="nonexistent")
        self.assertEqual(resp_unknown.status_code, status.HTTP_404_NOT_FOUND)

        resp_nw = self.client.get("/api/line-items/", HTTP_X_ORGANIZATION="northwind")
        self.assertEqual(resp_nw.status_code, status.HTTP_200_OK)
        nw_refs = {item["wire_reference"] for item in resp_nw.data}
        self.assertIn("CC-1001", nw_refs)
        self.assertNotIn("CC-2001", nw_refs)

        resp_bb = self.client.get("/api/line-items/", HTTP_X_ORGANIZATION="bluebird")
        self.assertEqual(resp_bb.status_code, status.HTTP_200_OK)
        bb_refs = {item["wire_reference"] for item in resp_bb.data}
        self.assertEqual(bb_refs, {"CC-2001"})

        csv_data = (
            "date,description,amount,type,reference\n"
            "2026-04-03,WIRE INCOMING RAHUL SHAH TRUST REF CC-1002,25000.00,credit,FT_ISOLATION\n"
        )
        self.csv_service_nw.parse_and_import(csv_data)
        txn_nw = BankTransaction.objects.get(bank_reference="FT_ISOLATION")
        match_nw = txn_nw.matches.first()

        resp_cross_approve = self.client.post(
            f"/api/matches/{match_nw.id}/approve/",
            HTTP_X_ORGANIZATION="bluebird",
        )
        self.assertEqual(resp_cross_approve.status_code, status.HTTP_404_NOT_FOUND)

        resp_cross_ignore = self.client.post(
            f"/api/transactions/{txn_nw.id}/ignore/",
            HTTP_X_ORGANIZATION="bluebird",
        )
        self.assertEqual(resp_cross_ignore.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_tenant_same_bank_reference_allowed(self):
        csv_data = (
            "date,description,amount,type,reference\n"
            "2026-04-01,WIRE SAME REF,5000.00,credit,SHARED_REF_123\n"
        )
        res_nw = self.csv_service_nw.parse_and_import(csv_data)
        res_bb = CsvImportService(self.org_bluebird).parse_and_import(csv_data)
        self.assertEqual(res_nw["imported_count"], 1)
        self.assertEqual(res_bb["imported_count"], 1)
        self.assertEqual(
            BankTransaction.objects.filter(bank_reference="SHARED_REF_123").count(),
            2,
        )


class TenantScopingTestCase(TestCase):
    def setUp(self):
        self.rf = APIRequestFactory()
        self.org_northwind = Organization.objects.create(
            slug="northwind",
            name="Northwind Ventures",
        )
        self.org_bluebird = Organization.objects.create(
            slug="bluebird",
            name="Bluebird Capital",
        )

    def test_missing_header_returns_400(self):
        request = self.rf.get("/test/")
        with self.assertRaises(MissingOrganizationHeader) as ctx:
            get_tenant_organization(request)
        self.assertEqual(ctx.exception.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_organization_returns_404(self):
        request = self.rf.get("/test/", HTTP_X_ORGANIZATION="unknown-org")
        with self.assertRaises(OrganizationNotFound) as ctx:
            get_tenant_organization(request)
        self.assertEqual(ctx.exception.status_code, status.HTTP_404_NOT_FOUND)

    def test_valid_header_resolves_organization(self):
        request = self.rf.get("/test/", HTTP_X_ORGANIZATION="northwind")
        org = get_tenant_organization(request)
        self.assertEqual(org, self.org_northwind)

    def test_view_missing_header_status_400(self):
        request = self.rf.get("/test/")
        view = DummyScopedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_view_unknown_org_status_404(self):
        request = self.rf.get("/test/", HTTP_X_ORGANIZATION="nonexistent")
        view = DummyScopedView.as_view()
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CsvImportEdgeCasesTestCase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            slug="northwind",
            name="Northwind Ventures",
        )
        self.service = CsvImportService(self.org)

    def test_debit_stored_as_ignored(self):
        csv_data = "date,description,amount,type,reference\n2026-04-05,BANK FEE,-25.00,debit,FEE01\n"
        result = self.service.parse_and_import(csv_data)
        self.assertEqual(result["imported_count"], 1)
        txn = BankTransaction.objects.get(bank_reference="FEE01")
        self.assertEqual(txn.status, BankTransaction.STATUS_IGNORED)
        self.assertEqual(txn.type, BankTransaction.TYPE_DEBIT)

    def test_import_sample_bank_statement_file(self):
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "sample_bank_statement.csv",
        )
        if not os.path.exists(sample_path):
            sample_path = "/app/../sample_bank_statement.csv"

        if os.path.exists(sample_path):
            with open(sample_path, "r", encoding="utf-8") as f:
                content = f.read()
            result = self.service.parse_and_import(content)
            self.assertEqual(result["duplicate_count"], 1)
            self.assertEqual(result["error_count"], 2)
            self.assertEqual(result["imported_count"], 11)
            error_lines = [err["line"] for err in result["errors"]]
            self.assertIn(13, error_lines)
            self.assertIn(14, error_lines)
            dup_lines = [d["line"] for d in result["duplicates"]]
            self.assertIn(11, dup_lines)


class MatchingEngineEdgeCasesTestCase(TestCase):
    def test_normalization_utilities(self):
        self.assertEqual(normalize_reference("cc-1003"), "CC1003")
        self.assertEqual(normalize_reference("Cc 1001"), "CC1001")
        self.assertEqual(normalize_investor_name("Haller Capital LLC"), "HALLER CAPITAL")
        self.assertEqual(normalize_investor_name("Patel Family Trust"), "PATEL FAMILY TRUST")
        self.assertEqual(normalize_investor_name("Meridian Partners LP"), "MERIDIAN PARTNERS")
        self.assertTrue(is_name_in_description("PATEL FAMILY TRUST", "WIRE INCOMING PATEL FAMILY TRUST"))
        self.assertFalse(is_name_in_description("PATEL FAMILY TRUST", "WIRE INCOMING PATEL FAMILY TRUSTEE"))
