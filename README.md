# Double-Entry Ledger

A backend for moving money between accounts using double-entry accounting — the model real banks and accounting systems use. Every transaction is recorded as matching debit and credit entries, balances are calculated from those entries instead of being stored, and transfers hold up when two of them hit the same account at once.

This is a simulated ledger for a portfolio project. Balances are fake and it's not wired to any real payment system.

**Live demo:** https://double-entry-ledger-yhor.onrender.com
(It's on a free tier, so the first request after it's been idle can take 30–60 seconds to wake up.)

---

## What it does

- Transfer money between accounts
- Deposit money into the ledger from a system account
- Read an account's balance

Every money movement is a double-entry transaction, so the books always balance.

---

## Design decisions

The reasoning behind the main choices, since that's the part that matters more than the CRUD.

### Double-entry so money can't appear from nowhere
Every transaction creates at least two entries — a debit and a credit — and they have to sum to zero for the transaction to go through. That's what stops "magical amounts." Money can't be created or destroyed, only moved: if Alice loses $100, another account gains exactly $100. A transaction that didn't sum to zero would mean something leaked.

This is also why entries are their own table instead of `from_account`/`to_account` columns on the transaction. Two columns only handle a two-sided transfer. Separate entries handle any number of sides — a $100 payment with a $3 fee is three entries (−100, +97, +3) that still sum to zero.

### Balance is calculated, not stored
An account's balance is the sum of its entries (credits minus debits), not a saved column. If it were a stored number, every transfer would have to update it, and two transfers running at once could update it wrong. Calculating it from the entries means there's no stored number to get corrupted — the balance is always whatever the entries add up to.

### Handling concurrent transfers
The problem: two transfers on the same account at the same time can both read the balance before either one saves, both pass the "enough funds?" check, and both go through — leaving the account overdrawn. Two things prevent that:

- `transaction.atomic()` wraps the whole transfer so it either fully commits or fully rolls back. No half-finished transfers.
- `select_for_update()` locks the account rows when they're read, so a second transfer has to wait for the first to finish, then reads the updated balance and fails correctly.

The funds check runs *after* the lock, so it reads the locked row. Running it before the lock would let the balance change underneath it — the lock is the thing that stops that.

### Locking accounts in id order
If two transfers locked the same two accounts in the opposite order, they'd each hold one and wait on the other forever — a deadlock. Locking accounts in a fixed order (sorted by id) means every transfer grabs locks in the same order, so that can't happen.

### Idempotency keys
Each transaction can carry a client-supplied key. If a transaction with that key already exists — say the client's connection dropped and it retried — the existing one is returned instead of running the transfer a second time. So a retry can't double-charge.

### Decimal, not float
Money uses `Decimal`. Floats can't hold values like 0.1 exactly, so amounts would drift off from what an account actually has or sends. Decimal keeps the math exact, which matters a lot when the whole point is that entries sum to exactly zero.

### How money gets in
Money has to enter a closed system from somewhere. A system account is that source — a deposit moves money from it into a user account. The system account is allowed to go negative, since its negative balance is just a running total of how much money is in circulation.

---

## Tech stack

- **Django** — models, migrations, admin, ORM
- **Django REST Framework** — the API
- **PostgreSQL** — the database. It's Postgres and not SQLite because the row-level locking (`SELECT FOR UPDATE`) that makes concurrent transfers safe needs it.
- **Gunicorn + WhiteNoise** — production server and static files
- **Render + Neon** — Render runs the app, Neon hosts the database

The business logic sits in a service layer (`ledger/services.py`) separate from the API views, so it can be tested and reused without going through HTTP.

---

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

Success returns `201`. Bad requests — not enough funds, bad amount, account that doesn't exist — return `400`. A balance lookup on a missing account returns `404`.

---

## Tests

There's a concurrency test that fires two transfers at the same account at the same time when it only has enough for one, and checks that exactly one goes through and the balance never drops below zero. Take out the row lock and the test fails (both go through, balance goes negative), which is the proof that the lock is what's holding the line.

```bash
python manage.py test ledger
```

---

## Running it locally

Needs Python 3.12+ and Docker (for Postgres).

```bash
# clone and enter
git clone https://github.com/lwilson-dev/double-entry-ledger.git
cd double-entry-ledger

# virtual environment
python3 -m venv .venv
source .venv/bin/activate

# dependencies
pip install -r requirements.txt

# start postgres
docker compose up -d

# make a .env file in the project root with:
#   SECRET_KEY=your-secret-key
#   DB_PASSWORD=ledgerpass
#   DEBUG=True
#   ALLOWED_HOSTS=127.0.0.1,localhost

# migrate
python manage.py migrate

# create the system account (money enters the ledger from here)
python manage.py shell
#   >>> from ledger.models import Account
#   >>> Account.objects.create(type="system", name="System")

# run
python manage.py runserver
```

API lives at `http://127.0.0.1:8000/api/`.

---

## Things I'd add next

- A database-level constraint to guarantee only one system account exists
- Balance snapshots so reads don't have to sum the whole entry history as it grows
- Auth on the API, with per-account permissions
- Pull the shared entry-creation code into one helper
