from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import TransferSerializer, DepositSerializer
from .services import transfer, deposit, get_balance
from .models import Account


@api_view(["POST"])
def create_transfer(request):
    serializer = TransferSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        txn = transfer(
            from_account_id=data["from_account_id"],
            to_account_id=data["to_account_id"],
            amount=data["amount"],
            the_idempotency_key=data["idempotency_key"],
        )
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {"transaction_id": txn.id, "description": txn.description},
        status=status.HTTP_201_CREATED,
    )

@api_view(["POST"])
def create_deposit(request):
    serializer = DepositSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = serializer.validated_data

    try:
        txn = deposit(
            to_account_id=data["to_account_id"],
            amount=data["amount"],
            the_idempotency_key=data["idempotency_key"],
        )
    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(
        {"transaction_id": txn.id, "description": txn.description},
        status=status.HTTP_201_CREATED,
    )

@api_view(["GET"])
def view_balance(request, account_id):
    try:
        account = Account.objects.get(id=account_id)
    except Account.DoesNotExist:
        return Response({"error": "account not found"}, status=status.HTTP_404_NOT_FOUND)

    balance = get_balance(account)
    return Response({"balance": balance})