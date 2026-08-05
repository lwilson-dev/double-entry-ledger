from django.urls import path
from . import views

urlpatterns = [
    path("transfers/", views.create_transfer, name="create-transfer"),
    path("deposits/", views.create_deposit, name="create-deposit"),
    path("balance/<int:account_id>/", views.view_balance, name="view-balance")
]