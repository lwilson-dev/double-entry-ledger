# Double-Entry Ledger

A backend for moving money between accounts using double-entry accounting, the same model banks and accounting systems use. Every transaction records matching debit and credit entries, account balances are calculated from those entries rather than stored, and transfers stay correct when two of them hit the same account at the same time.

This is a simulated ledger built as a portfolio project. The balances are fake and it isn't connected to any real payment system.

Live demo: https://double-entry-ledger-yhor.onrender.com (free tier, so the first request after it's been idle can take up to a minute to wake up)

## What it does

- Transfer money between accounts
- Deposit money into the ledger from a system account
- Look up an account's balance

Every money movement is a double-entry transaction, so the books always balance.

## How it works

### Double-entry

Every transaction creates at least two entries, a debit and a credit, and they have to add up to zero for the transaction to go through. This is what keeps money from appearing out of nowhere. If one account loses $100, another account gains exactly $100. A transaction whose entries didn't sum to zero would mean something went wrong.

Entries live in their own table instead of being `from_account` and `to_account` columns on the transaction. Two columns can only describe a two-sided transfer, but a real transaction isn't always two-sided. A $100 payment with a $3 fee is three entries (-100, +97, +3) that still add up to zero, and separate entries handle that fine.

### Calculated balances

An account's balance is the sum of its entries (credits minus debits) rather than a saved column. A stored balance would have to be updated on every transfer, and two transfers running at once could update it incorrectly. Calculating it from the entries means there's no saved number to get out of sync.

### Concurrent transfers

Two transfers on the same account at the same time can both read the balance before either one finishes, both decide there's enough money, and both go through, leaving the account overdrawn. Two things stop that:

- `transaction.atomic()` wraps the whole transfer so it either fully commits or fully rolls back. A transfer can't be left half done.
- `select_for_update()` locks the account rows when they're read, so the second transfer waits for the first to finish, then reads the updated balance and correctly fails.

The funds check runs after the lock, so it reads the locked row. If it ran before the lock, the balance could change underneath it.

### Avoiding deadlocks

If two transfers locked the same two accounts in opposite orders, each would hold one lock and wait forever on the other. Locking accounts in a fixed order (by id) means every transfer takes its locks in the same order, so that can't happen.

### Idempotency

A transaction can include a key supplied by the client. If a transaction with that key already exists, say because a dropped connection made the client retry, the existing transaction is returned instead of running the transfer again. A retry can't double-charge.

### Decimal instead of float

Money uses `Decimal`. Floats can't store values like 0.1 exactly, so amounts would drift away from what an account actually holds. Decimal keeps the arithmetic exact, which matters when the whole thing depends on entries summing to exactly zero.

### Getting money in

Money has to come from somewhere in a closed system. A system account is the source: a deposit moves money from it into a user account. The system account is allowed to go negative, because its negative balance is just a running total of how much money is in circulation.

## Tech stack

- Django for models, migrations, admin, and the ORM
- Django REST Framework for the API
- PostgreSQL for the database
- Gunicorn and WhiteNoise for serving in production
- Render for hosting, Neon for the managed PostgreSQL database

The business logic lives in a service layer (`ledger/services.py`) kept separate from the API views, so it can be tested and reused without going through HTTP.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/transfers/` | Move money between two accounts |
| `POST` | `/api/deposits/` | Deposit from the system account into a user account |
| `GET`  | `/api/accounts/<id>/balance/` | Get an account's balance |

Example transfer:

```
POST /api/transfers/
Content-Type: application/json

{
  "from_account_id": 2,
  "to_account_id": 3,
  "amount": "40.00",
  "idempotency_key": "transfer-abc-123"
}
```

A successful transfer returns `201`. Bad requests like insufficient funds, a bad amount, or an account that doesn't exist return `400`. A balance lookup on a missing account returns `404`.

## Tests

There's a concurrency test that fires two transfers at the same account at the same time when it only has enough for one, and checks that exactly one goes through and the balance never drops below zero. If you take out the row lock, the test fails (both go through and the balance goes negative), which shows the lock is what's preventing the overdraw.

```bash
python manage.py test ledger
```

## Running it locally

You'll need Python 3.12+ and Docker (for PostgreSQL).

```bash
git clone https://github.com/lwilson-dev/double-entry-ledger.git
cd double-entry-ledger

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

docker compose up -d

# create a .env file in the project root with:
#   SECRET_KEY=your-secret-key
#   DB_PASSWORD=ledgerpass
#   DEBUG=True
#   ALLOWED_HOSTS=127.0.0.1,localhost

python manage.py migrate

# create the system account (money enters the ledger from here)
python manage.py shell
#   >>> from ledger.models import Account
#   >>> Account.objects.create(type="system", name="System")

python manage.py runserver
```

The API runs at `http://127.0.0.1:8000/api/`.
