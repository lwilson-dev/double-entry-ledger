from django.db import models
from django.conf import settings

# Create your models here.

class Account(models.Model):
    class Type(models.TextChoices):
        USER = ("user", "User")
        SYSTEM = ("system", "System")
        FEE = ("fee", "Fee")
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name = "accounts"
    )

    type = models.CharField(max_length=20, choices=Type.choices)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class Transaction(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name = "transactions",
        )
    idempotency_key = models.CharField(unique=True, max_length=255, null=True, blank=True)
    def __str__(self):
        return self.description

class Entry(models.Model):
    class Direction(models.TextChoices):
        DEBIT = ("debit","Debit")
        CREDIT = ("credit", "Credit")

    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name = "entries"
        )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name = "entries"
        )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    direction = models.CharField(max_length=20,choices=Direction.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.get_direction_display()} {self.amount}"

    #which transaction it belongs to
    #what single account it touches
    # amount
    # direction (debit or credit)    

