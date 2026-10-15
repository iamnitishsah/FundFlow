from django.urls import path
from .views import (
    OrganizationListView,
    LineItemListView,
    BankTransactionListView,
    StatementUploadView,
    ApproveMatchView,
    RejectMatchView,
    IgnoreTransactionView,
)

urlpatterns = [
    path("organizations/", OrganizationListView.as_view(), name="organization-list"),
    path("line-items/", LineItemListView.as_view(), name="line-item-list"),
    path("transactions/", BankTransactionListView.as_view(), name="transaction-list"),
    path("statements/upload/", StatementUploadView.as_view(), name="statement-upload"),
    path("matches/<int:match_id>/approve/", ApproveMatchView.as_view(), name="match-approve"),
    path("matches/<int:match_id>/reject/", RejectMatchView.as_view(), name="match-reject"),
    path("transactions/<int:transaction_id>/ignore/", IgnoreTransactionView.as_view(), name="transaction-ignore"),
]
