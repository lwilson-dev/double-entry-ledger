from django.test import TestCase
import threading
from decimal import Decimal

from django.test import TransactionTestCase #Django test class for when you need to test actual database transactions.
#Needed because using TestCase leads to data not actually being committed, which doesn't allow me to do the ConcurrencyTest fully
from django.db import connection

from ledger.models import Account
from ledger.services import transfer, deposit, get_balance


class ConcurrencyTest(TransactionTestCase):

    def test_concurrent_transfers_cannot_overdraw(self):
        system = Account.objects.create(type="system", name="System")
        alice = Account.objects.create(type="user", name="Alice")
        bob = Account.objects.create(type="user", name="Bob")

        # fund Alice with enough for only one transfer
        deposit(alice.id, Decimal("100"), "seed-alice")

        results = []
        barrier = threading.Barrier(2)   # gate for 2 threads


        def do_transfer(key):
            barrier.wait()     # both threads line up here. First one will wait for the other and then be released together at the same time
            try:
                transfer(alice.id, bob.id, Decimal("100"), key)
                results.append("ok")
            except ValueError:
                results.append("failed")
            finally:
                connection.close()   # each thread closes its own connection

        t1 = threading.Thread(target=do_transfer, args=("race-1",))
        t2 = threading.Thread(target=do_transfer, args=("race-2",))
        t1.start(); t2.start()
        t1.join(); t2.join() #makes it so the code continues only after the threads have finished running. Without this, assertions may run without the threads even being finished

        
        self.assertEqual(results.count("ok"), 1) 
        self.assertEqual(results.count("failed"), 1) 

        # checking that Alice never went negative
        self.assertEqual(get_balance(alice), Decimal("0"))
        self.assertEqual(get_balance(bob), Decimal("100"))