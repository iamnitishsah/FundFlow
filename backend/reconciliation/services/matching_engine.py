import re
from decimal import Decimal
from typing import List, Optional
from reconciliation.models import (
    BankTransaction,
    LineItem,
    MatchProposal,
)


def normalize_reference(raw_ref: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw_ref).upper()


def normalize_investor_name(raw_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", raw_name).strip().upper()
    tokens = cleaned.split()
    if tokens and tokens[-1] in {"LLC", "LP", "LTD", "INC"}:
        tokens.pop()
    return " ".join(tokens)


def is_name_in_description(normalized_name: str, normalized_desc: str) -> bool:
    if not normalized_name or not normalized_desc:
        return False
    pattern = r"\b" + re.escape(normalized_name) + r"\b"
    return bool(re.search(pattern, normalized_desc))


class MatchingEngineService:
    def process_transaction(self, transaction: BankTransaction) -> BankTransaction:
        if transaction.type == BankTransaction.TYPE_DEBIT:
            transaction.status = BankTransaction.STATUS_IGNORED
            transaction.needs_review_reason = ""
            transaction.save()
            return transaction

        eligible_items = list(
            LineItem.objects.filter(
                capital_call__organization=transaction.organization,
                capital_call__call_date__lte=transaction.date,
            ).select_related("capital_call", "investor_entity")
        )
        eligible_items = [
            item for item in eligible_items
            if item.amount_remaining > Decimal("0.00")
        ]

        norm_desc_ref = normalize_reference(transaction.description)
        norm_bank_ref = normalize_reference(transaction.bank_reference)

        ref_matches = []
        for item in eligible_items:
            norm_item_ref = normalize_reference(item.wire_reference)
            if norm_item_ref and (norm_item_ref in norm_desc_ref or norm_item_ref in norm_bank_ref):
                ref_matches.append(item)

        if len(ref_matches) == 1:
            matched_item = ref_matches[0]
            if transaction.amount <= matched_item.amount_remaining:
                transaction.status = BankTransaction.STATUS_SUGGESTED
                transaction.needs_review_reason = ""
                transaction.save()
                MatchProposal.objects.create(
                    transaction=transaction,
                    line_item=matched_item,
                    match_status=MatchProposal.STATUS_PROPOSED,
                    reason=(
                        f"Reference {matched_item.wire_reference} found; "
                        f"amount {transaction.amount} is within remaining {matched_item.amount_remaining}."
                    ),
                )
            else:
                transaction.status = BankTransaction.STATUS_NEEDS_REVIEW
                transaction.needs_review_reason = (
                    f"Overpayment: Reference {matched_item.wire_reference} found, but "
                    f"amount {transaction.amount} exceeds remaining {matched_item.amount_remaining}."
                )
                transaction.save()
            return transaction

        elif len(ref_matches) > 1:
            transaction.status = BankTransaction.STATUS_NEEDS_REVIEW
            ref_names = ", ".join(item.wire_reference for item in ref_matches)
            transaction.needs_review_reason = (
                f"Multiple reference matches found: {ref_names}."
            )
            transaction.save()
            for item in ref_matches:
                MatchProposal.objects.create(
                    transaction=transaction,
                    line_item=item,
                    match_status=MatchProposal.STATUS_PROPOSED,
                    reason=(
                        f"Reference {item.wire_reference} found in description or bank reference."
                    ),
                )
            return transaction

        name_amount_matches = []
        for item in eligible_items:
            if item.amount_remaining == transaction.amount:
                norm_inv_name = item.investor_entity.normalized_name or normalize_investor_name(
                    item.investor_entity.name
                )
                if is_name_in_description(norm_inv_name, transaction.normalized_description):
                    name_amount_matches.append(item)

        if len(name_amount_matches) == 1:
            matched_item = name_amount_matches[0]
            transaction.status = BankTransaction.STATUS_SUGGESTED
            transaction.needs_review_reason = ""
            transaction.save()
            MatchProposal.objects.create(
                transaction=transaction,
                line_item=matched_item,
                match_status=MatchProposal.STATUS_PROPOSED,
                reason=(
                    f"Investor name '{matched_item.investor_entity.name}' found and "
                    f"amount equals remaining {matched_item.amount_remaining}."
                ),
            )
        elif len(name_amount_matches) > 1:
            transaction.status = BankTransaction.STATUS_NEEDS_REVIEW
            refs = ", ".join(item.wire_reference for item in name_amount_matches)
            transaction.needs_review_reason = (
                f"Multiple line items matched investor name and remaining amount: {refs}."
            )
            transaction.save()
            for item in name_amount_matches:
                MatchProposal.objects.create(
                    transaction=transaction,
                    line_item=item,
                    match_status=MatchProposal.STATUS_PROPOSED,
                    reason=(
                        f"Investor name '{item.investor_entity.name}' found and "
                        f"amount equals remaining {item.amount_remaining}."
                    ),
                )
        else:
            transaction.status = BankTransaction.STATUS_NEEDS_REVIEW
            transaction.needs_review_reason = (
                "No eligible line items matched by reference or investor name and amount."
            )
            transaction.save()

        return transaction

    def process_transactions(self, transactions: List[BankTransaction]) -> List[BankTransaction]:
        return [self.process_transaction(txn) for txn in transactions]

