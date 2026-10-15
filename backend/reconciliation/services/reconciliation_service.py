from decimal import Decimal
from django.db import transaction
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound
from reconciliation.models import (
    Organization,
    BankTransaction,
    LineItem,
    MatchProposal,
)


class ReconciliationConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict during reconciliation action."
    default_code = "reconciliation_conflict"


class ReconciliationService:
    def __init__(self, organization: Organization):
        self.organization = organization

    def approve_match(self, match_id: int) -> MatchProposal:
        with transaction.atomic():
            try:
                match = (
                    MatchProposal.objects.select_for_update()
                    .select_related("transaction", "line_item")
                    .get(id=match_id)
                )
            except MatchProposal.DoesNotExist:
                raise NotFound("Match proposal not found.")

            if match.transaction.organization_id != self.organization.id:
                raise NotFound("Match proposal not found.")

            txn = (
                BankTransaction.objects.select_for_update()
                .get(id=match.transaction_id)
            )
            line_item = (
                LineItem.objects.select_for_update()
                .get(id=match.line_item_id)
            )

            if txn.status == BankTransaction.STATUS_RECONCILED:
                raise ReconciliationConflictError("Transaction is already reconciled.")

            if match.match_status != MatchProposal.STATUS_PROPOSED:
                raise ReconciliationConflictError(
                    f"Match proposal cannot be approved in '{match.match_status}' state."
                )

            if txn.amount > line_item.amount_remaining:
                raise ReconciliationConflictError(
                    f"Transaction amount {txn.amount} exceeds remaining amount {line_item.amount_remaining}."
                )

            line_item.amount_funded += txn.amount
            line_item.update_status()
            line_item.save(update_fields=["amount_funded", "status", "updated_at"])

            match.match_status = MatchProposal.STATUS_APPROVED
            match.save(update_fields=["match_status", "updated_at"])

            MatchProposal.objects.filter(
                transaction=txn,
                match_status=MatchProposal.STATUS_PROPOSED,
            ).exclude(id=match.id).update(
                match_status=MatchProposal.STATUS_REJECTED
            )

            txn.status = BankTransaction.STATUS_RECONCILED
            txn.needs_review_reason = ""
            txn.save(update_fields=["status", "needs_review_reason", "updated_at"])

            return match

    def reject_match(self, match_id: int) -> MatchProposal:
        with transaction.atomic():
            try:
                match = (
                    MatchProposal.objects.select_for_update()
                    .select_related("transaction")
                    .get(id=match_id)
                )
            except MatchProposal.DoesNotExist:
                raise NotFound("Match proposal not found.")

            if match.transaction.organization_id != self.organization.id:
                raise NotFound("Match proposal not found.")

            txn = (
                BankTransaction.objects.select_for_update()
                .get(id=match.transaction_id)
            )

            if txn.status == BankTransaction.STATUS_RECONCILED:
                raise ReconciliationConflictError(
                    "Cannot reject a match on a reconciled transaction."
                )

            match.match_status = MatchProposal.STATUS_REJECTED
            match.save(update_fields=["match_status", "updated_at"])

            has_proposed = MatchProposal.objects.filter(
                transaction=txn,
                match_status=MatchProposal.STATUS_PROPOSED,
            ).exists()

            if not has_proposed:
                txn.status = BankTransaction.STATUS_NEEDS_REVIEW
                if not txn.needs_review_reason:
                    txn.needs_review_reason = "Match was rejected."
                txn.save(update_fields=["status", "needs_review_reason", "updated_at"])

            return match

    def ignore_transaction(self, transaction_id: int) -> BankTransaction:
        with transaction.atomic():
            try:
                txn = (
                    BankTransaction.objects.select_for_update()
                    .get(id=transaction_id)
                )
            except BankTransaction.DoesNotExist:
                raise NotFound("Transaction not found.")

            if txn.organization_id != self.organization.id:
                raise NotFound("Transaction not found.")

            if txn.status == BankTransaction.STATUS_RECONCILED:
                raise ReconciliationConflictError("Cannot ignore a reconciled transaction.")

            txn.status = BankTransaction.STATUS_IGNORED
            txn.save(update_fields=["status", "updated_at"])

            MatchProposal.objects.filter(
                transaction=txn,
                match_status=MatchProposal.STATUS_PROPOSED,
            ).update(match_status=MatchProposal.STATUS_REJECTED)

            return txn

