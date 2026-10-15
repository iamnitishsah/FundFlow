from rest_framework import status
from rest_framework.exceptions import APIException
from .models import (
    Organization,
    CapitalCall,
    InvestorEntity,
    LineItem,
    BankTransaction,
    MatchProposal,
)


class MissingOrganizationHeader(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "X-Organization header is required."
    default_code = "missing_organization_header"


class OrganizationNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "Organization not found."
    default_code = "organization_not_found"


def get_tenant_organization(request) -> Organization:
    raw_header = request.headers.get("X-Organization")
    if not raw_header:
        raw_header = request.META.get("HTTP_X_ORGANIZATION")

    if not raw_header or not raw_header.strip():
        raise MissingOrganizationHeader()

    slug = raw_header.strip()
    try:
        return Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        raise OrganizationNotFound()


class TenantScopedMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.organization = get_tenant_organization(request)
        request.organization = self.organization

    def get_queryset(self):
        if hasattr(super(), "get_queryset"):
            qs = super().get_queryset()
        elif hasattr(self, "queryset") and self.queryset is not None:
            qs = self.queryset.all()
        else:
            raise NotImplementedError("View must define queryset or get_queryset.")

        model = qs.model
        if model is Organization:
            return qs.filter(id=self.organization.id)
        elif model is CapitalCall:
            return qs.filter(organization=self.organization)
        elif model is InvestorEntity:
            return qs.filter(organization=self.organization)
        elif model is LineItem:
            return qs.filter(capital_call__organization=self.organization)
        elif model is BankTransaction:
            return qs.filter(organization=self.organization)
        elif model is MatchProposal:
            return qs.filter(transaction__organization=self.organization)

        if hasattr(model, "organization"):
            return qs.filter(organization=self.organization)

        return qs

