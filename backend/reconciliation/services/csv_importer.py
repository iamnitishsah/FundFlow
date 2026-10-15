import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Any, Union
from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import APIException
from reconciliation.models import Organization, BankTransaction
from .matching_engine import MatchingEngineService


class MissingCsvColumnError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Missing required CSV column."
    default_code = "missing_csv_column"


class CsvImportService:
    REQUIRED_COLUMNS = ["date", "description", "amount", "type", "reference"]

    def __init__(self, organization: Organization):
        self.organization = organization
        self.matching_engine = MatchingEngineService()

    def parse_and_import(
        self,
        file_obj: Union[io.TextIOBase, io.BufferedIOBase, str, bytes],
    ) -> Dict[str, Any]:
        if isinstance(file_obj, bytes):
            content = file_obj.decode("utf-8-sig")
            stream = io.StringIO(content)
        elif isinstance(file_obj, str):
            stream = io.StringIO(file_obj)
        elif hasattr(file_obj, "read"):
            raw_data = file_obj.read()
            if isinstance(raw_data, bytes):
                content = raw_data.decode("utf-8-sig")
            else:
                content = raw_data
            stream = io.StringIO(content)
        else:
            raise ValueError("Unsupported file object type.")

        reader = csv.reader(stream)
        try:
            raw_headers = next(reader)
        except StopIteration:
            raise MissingCsvColumnError("The CSV file is empty.")

        header_map = {}
        for idx, h in enumerate(raw_headers):
            clean_header = h.strip().lower()
            header_map[clean_header] = idx

        for col in self.REQUIRED_COLUMNS:
            if col not in header_map:
                raise MissingCsvColumnError(f"Missing required column: '{col}'")

        seen_in_file_refs = set()
        existing_db_refs = set(
            BankTransaction.objects.filter(
                organization=self.organization,
            ).values_list("bank_reference", flat=True)
        )

        valid_rows_to_create = []
        errors = []
        duplicates = []
        line_number = 1

        for row in reader:
            line_number += 1
            if not row or all(not cell.strip() for cell in row):
                continue

            max_needed_idx = max(header_map[col] for col in self.REQUIRED_COLUMNS)
            if len(row) <= max_needed_idx:
                errors.append({
                    "line": line_number,
                    "message": f"Row has insufficient columns ({len(row)} found)",
                })
                continue

            raw_date = row[header_map["date"]].strip()
            raw_desc = row[header_map["description"]].strip()
            raw_amount = row[header_map["amount"]].strip()
            raw_type = row[header_map["type"]].strip()
            raw_ref = row[header_map["reference"]].strip()

            row_errors = []

            if not raw_desc:
                row_errors.append("Description is required")

            if not raw_ref:
                row_errors.append("Reference is required")

            parsed_date = None
            if not raw_date:
                row_errors.append("Date is required")
            else:
                try:
                    parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    row_errors.append(f"Invalid date format or calendar date: '{raw_date}'")

            parsed_amount = None
            if not raw_amount:
                row_errors.append("Amount is required")
            else:
                clean_amount_str = raw_amount.replace(",", "")
                try:
                    parsed_amount = Decimal(clean_amount_str)
                    if parsed_amount == Decimal("0.00"):
                        row_errors.append("Amount cannot be zero")
                except (InvalidOperation, ValueError):
                    row_errors.append(f"Invalid amount value: '{raw_amount}'")

            clean_type = raw_type.lower()
            if clean_type not in ("credit", "debit"):
                row_errors.append(f"Type must be 'credit' or 'debit', got '{raw_type}'")
            elif parsed_amount is not None:
                if clean_type == "credit" and parsed_amount <= Decimal("0.00"):
                    row_errors.append("Credit amount must be positive")
                elif clean_type == "debit" and parsed_amount >= Decimal("0.00"):
                    row_errors.append("Debit amount must be negative")

            if row_errors:
                errors.append({
                    "line": line_number,
                    "message": "; ".join(row_errors),
                })
                continue

            if raw_ref in seen_in_file_refs:
                duplicates.append({
                    "line": line_number,
                    "reference": raw_ref,
                    "message": f"Duplicate bank reference in file: '{raw_ref}'",
                })
                continue

            if raw_ref in existing_db_refs:
                duplicates.append({
                    "line": line_number,
                    "reference": raw_ref,
                    "message": f"Duplicate bank reference already imported: '{raw_ref}'",
                })
                continue

            seen_in_file_refs.add(raw_ref)

            if clean_type == "debit":
                initial_status = BankTransaction.STATUS_IGNORED
            else:
                initial_status = BankTransaction.STATUS_NEEDS_REVIEW

            valid_rows_to_create.append({
                "organization": self.organization,
                "date": parsed_date,
                "description": raw_desc,
                "amount": parsed_amount,
                "type": clean_type,
                "bank_reference": raw_ref,
                "status": initial_status,
                "raw_file_line": line_number,
            })

        created_transactions = []
        with transaction.atomic():
            for row_data in valid_rows_to_create:
                txn = BankTransaction.objects.create(**row_data)
                created_transactions.append(txn)

            for txn in created_transactions:
                if txn.type == BankTransaction.TYPE_CREDIT:
                    self.matching_engine.process_transaction(txn)

        return {
            "imported_count": len(created_transactions),
            "duplicate_count": len(duplicates),
            "error_count": len(errors),
            "errors": errors,
            "duplicates": duplicates,
            "created_transactions": created_transactions,
        }
