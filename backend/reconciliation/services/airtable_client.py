import os
import requests
from typing import Optional
from reconciliation.models import BankTransaction


class RealAirtableClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_id: Optional[str] = None,
        table_name: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("AIRTABLE_API_KEY", "")
        self.base_id = base_id or os.environ.get("AIRTABLE_BASE_ID", "")
        self.table_name = (
            table_name
            or os.environ.get("AIRTABLE_TABLE_NAME", "Needs Review Transactions")
        )

    def create_record(self, transaction: BankTransaction) -> str:
        if not self.api_key or not self.base_id:
            raise ValueError("Airtable credentials not configured.")

        url = f"https://api.airtable.com/v0/{self.base_id}/{self.table_name}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "fields": {
                "Organization": transaction.organization.slug,
                "Date": str(transaction.date),
                "Description": transaction.description,
                "Amount": float(transaction.amount),
                "Type": transaction.type,
                "Bank Reference": transaction.bank_reference,
                "Reason": transaction.needs_review_reason,
            }
        }
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("id", "")


class FakeAirtableClient:
    def __init__(
        self,
        should_fail: bool = False,
        record_id: str = "recFake1234567890",
    ):
        self.should_fail = should_fail
        self.record_id = record_id
        self.created_records = []

    def create_record(self, transaction: BankTransaction) -> str:
        if self.should_fail:
            raise ConnectionError("Simulated Airtable connection failure.")
        self.created_records.append(transaction)
        return self.record_id


class AirtableSyncService:
    def __init__(self, client=None):
        self.client = client or RealAirtableClient()

    def sync_transaction(self, transaction: BankTransaction) -> BankTransaction:
        if transaction.status != BankTransaction.STATUS_NEEDS_REVIEW:
            return transaction

        try:
            record_id = self.client.create_record(transaction)
            transaction.airtable_record_id = record_id
            transaction.airtable_sync_status = "synced"
            transaction.airtable_error = ""
        except Exception as exc:
            transaction.airtable_sync_status = "sync_failed"
            transaction.airtable_error = str(exc)

        transaction.save(
            update_fields=[
                "airtable_record_id",
                "airtable_sync_status",
                "airtable_error",
                "updated_at",
            ]
        )
        return transaction

