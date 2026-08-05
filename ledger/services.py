from decimal import Decimal

from .models import Account, Transaction, Entry
from django.db.models import Sum, Case, When, F, DecimalField
from django.db import transaction #from django not our model

def get_balance(account): 
    """Return the current balance of an account by summing its ledger entries."""
    result = account.entries.aggregate(
        balance=Sum(
            Case(
                When(direction="credit", then=F("amount")),
                When(direction="debit", then=-F("amount")),
                output_field=DecimalField(),
            )
        )
    )
    return result["balance"] or Decimal("0")

@transaction.atomic #Either everything in this function succeeds, or none of it does
def transfer(from_account_id, to_account_id, amount, the_idempotency_key, user=None):
    """Transfer funds between two accounts using a double-entry transaction."""
    existing = Transaction.objects.filter(idempotency_key=the_idempotency_key).first()
    if existing:
        return existing

    accounts = list( #order the accounts by id so no deadlocks happen
        Account.objects.select_for_update()
        .filter(id__in=[from_account_id, to_account_id])
        .order_by("id")
    )
    if len(accounts) != 2:
        raise ValueError("one or both accounts don't exist")
    
    by_id = {a.id: a for a in accounts} #dictionary for both accounts
    source = by_id[from_account_id]
    destination = by_id[to_account_id]
   
    
    if amount <= 0:
        raise ValueError("amount is negative or 0")
         
    if get_balance(source) < amount: # balance check comes after row lock because the balance could potentially change  
        raise ValueError("Amount is greater than balance")

    txn = Transaction.objects.create(
        description=f"{source.name} sent {amount} to {destination.name}",
        idempotency_key = the_idempotency_key,
        created_by = user,
    )

    Entry.objects.create(
        transaction = txn,
        amount = amount,
        direction = "debit",
        account = source
    )
    Entry.objects.create(
        transaction = txn,
        amount = amount,
        direction = "credit",
        account = destination
    )

    return txn

@transaction.atomic
def deposit(to_account_id, amount, the_idempotency_key, user=None):
    """Deposit funds from the system account into a user account.
        Only a system account is allowed to go negative"""

    existing = Transaction.objects.filter(idempotency_key=the_idempotency_key).first()
    if existing:
        return existing

    system_id = Account.objects.filter(type="system").values_list("id", flat=True).first()
    if system_id is None:
        raise ValueError("system account doesn't exist")

    accounts = list( #
        Account.objects.select_for_update()
        .filter(id__in=[system_id, to_account_id])
        .order_by("id")
    )

    if len(accounts) != 2:
            raise ValueError("one or both accounts don't exist")

    by_id = {a.id: a for a in accounts} #dictionary for both accounts
    source = by_id[system_id]
    destination = by_id[to_account_id]

    if amount <= 0:
        raise ValueError("amount is negative or 0")

    txn = Transaction.objects.create(
        description=f"{source.name} sent {amount} to {destination.name}",
        idempotency_key = the_idempotency_key,
        created_by = user,
    )

    Entry.objects.create(
        transaction = txn,
        amount = amount,
        direction = "debit",
        account = source
    )
    Entry.objects.create(
        transaction = txn,
        amount = amount,
        direction = "credit",
        account = destination
    )

    return txn

    


