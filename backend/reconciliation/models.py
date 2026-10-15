import re
from decimal import Decimal
from django.db import models


class Organization(models.Model):
    slug = models.SlugField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.slug})"


class CapitalCall(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="capital_calls",
    )
    call_number = models.PositiveIntegerField()
    call_date = models.DateField()
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["call_date", "call_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "call_number"],
                name="unique_org_call_number",
            )
        ]

    def __str__(self):
        return f"{self.organization.slug} - Capital Call #{self.call_number}"


class InvestorEntity(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="investor_entities",
    )
    name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_org_investor_name",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.normalized_name:
            self.normalized_name = self.normalize_name(self.name)
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_name(raw_name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", " ", raw_name).strip().upper()
        tokens = cleaned.split()
        if tokens and tokens[-1] in {"LLC", "LP", "LTD", "INC"}:
            tokens.pop()
        return " ".join(tokens)

    def __str__(self):
        return self.name


class LineItem(models.Model):
    STATUS_OPEN = "open"
    STATUS_PARTIALLY_FUNDED = "partially_funded"
    STATUS_FUNDED = "funded"
    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_PARTIALLY_FUNDED, "Partially Funded"),
        (STATUS_FUNDED, "Funded"),
    ]

    capital_call = models.ForeignKey(
        CapitalCall,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    investor_entity = models.ForeignKey(
        InvestorEntity,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    wire_reference = models.CharField(max_length=100, db_index=True)
    normalized_reference = models.CharField(max_length=100, db_index=True)
    amount_called = models.DecimalField(max_digits=14, decimal_places=2)
    amount_funded = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capital_call", "wire_reference"]
        constraints = [
            models.UniqueConstraint(
                fields=["capital_call", "wire_reference"],
                name="unique_call_wire_reference",
            )
        ]

    @property
    def amount_remaining(self) -> Decimal:
        return self.amount_called - self.amount_funded

    def update_status(self):
        if self.amount_funded <= Decimal("0.00"):
            self.status = self.STATUS_OPEN
        elif self.amount_funded >= self.amount_called:
            self.status = self.STATUS_FUNDED
        else:
            self.status = self.STATUS_PARTIALLY_FUNDED

    def save(self, *args, **kwargs):
        if not self.normalized_reference:
            self.normalized_reference = re.sub(
                r"[^A-Za-z0-9]",
                "",
                self.wire_reference.upper(),
            )
        self.update_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.wire_reference} - {self.investor_entity.name} ({self.status})"


class BankTransaction(models.Model):
    TYPE_CREDIT = "credit"
    TYPE_DEBIT = "debit"
    TYPE_CHOICES = [
        (TYPE_CREDIT, "Credit"),
        (TYPE_DEBIT, "Debit"),
    ]

    STATUS_SUGGESTED = "suggested"
    STATUS_NEEDS_REVIEW = "needs_review"
    STATUS_RECONCILED = "reconciled"
    STATUS_IGNORED = "ignored"
    STATUS_CHOICES = [
        (STATUS_SUGGESTED, "Suggested"),
        (STATUS_NEEDS_REVIEW, "Needs Review"),
        (STATUS_RECONCILED, "Reconciled"),
        (STATUS_IGNORED, "Ignored"),
    ]

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    date = models.DateField(db_index=True)
    description = models.TextField()
    normalized_description = models.TextField(blank=True, default="")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    bank_reference = models.CharField(max_length=100, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
    )
    needs_review_reason = models.TextField(blank=True, default="")
    raw_file_line = models.PositiveIntegerField(null=True, blank=True)
    airtable_record_id = models.CharField(max_length=100, blank=True, default="")
    airtable_sync_status = models.CharField(
        max_length=20,
        choices=[
            ("not_synced", "Not Synced"),
            ("synced", "Synced"),
            ("sync_failed", "Sync Failed"),
        ],
        default="not_synced",
    )
    airtable_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "bank_reference"],
                name="unique_org_bank_reference",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.normalized_description:
            self.normalized_description = re.sub(
                r"[^A-Za-z0-9]+",
                " ",
                self.description,
            ).strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} {self.bank_reference} ({self.amount}) - {self.status}"


class MatchProposal(models.Model):
    STATUS_PROPOSED = "proposed"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PROPOSED, "Proposed"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    line_item = models.ForeignKey(
        LineItem,
        on_delete=models.CASCADE,
        related_name="match_proposals",
    )
    match_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PROPOSED,
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "line_item"],
                name="unique_transaction_line_item",
            )
        ]

    def __str__(self):
        return f"{self.transaction.bank_reference} -> {self.line_item.wire_reference} [{self.match_status}]"
