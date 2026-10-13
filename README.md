# Mavumbi Sports Club Management System

Desktop application (Python, PySide6) backed by MySQL. Built around one shared **Person** table and one
append-only **ledger**, so total income is a query, not a formula maintained in many places.

## Modules
| Tab | Does |
|---|---|
| Members | Enrol members (12-35), 3 ranked games, groups at Ksh 500 each, age category derived from date of birth |
| Store & merchandise | Cart, 5% discount above Ksh 10,000, variable shoe pricing, cash/M-Pesa, stock history, 20% re-order alerts, fan jersey sales |
| Events & fees | Fixtures, team and captain, Ksh 500 facilitation fee per player (external fixtures), patron 20% commission, ticket sales |
| Equipment | Club equipment, issue to captain, return with lost/damaged, surcharge = market value + 10% split across the team |
| Football ops | Squads per season, contracts (amateur/youth/professional) with monthly wages, injuries (injured players cannot be selected), match results with player stats, club record and top scorers |
| Finance | Income summary (now net of wages) (gross/net) by period, sponsors and sponsorship received |
| Reports | 17 reports, export to CSV and Excel |

Roles: **admin / manager** (everything), **clerk** (members, store), **patron** (members, events, equipment, football ops; cannot pay wages).

## Upgrading an existing database
Pull the new code, then run `python manage.py init-db` again. It only ADDS the new tables; existing data is untouched.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
1. Create the database and a user in MySQL 8 / MariaDB 10.6+:
   ```sql
   CREATE DATABASE mavumbi_club CHARACTER SET utf8mb4;
   CREATE USER 'mavumbi'@'localhost' IDENTIFIED BY 'a-strong-password';
   GRANT ALL ON mavumbi_club.* TO 'mavumbi'@'localhost';
   ```
2. `cp .env.example .env` and fill in the credentials.
3. `python manage.py init-db` (creates tables, loads the 15 games, roles, price list, sample equipment).
4. `python manage.py create-user admin --role admin` (prompts for a password).
5. Optional: `python manage.py demo-data`, then `python main.py`.

Without MySQL you can try it on SQLite: set `MAVUMBI_DB_URL=sqlite:///mavumbi_dev.db` in `.env`.

## Tests
```bash
pytest                                   # fast, in-memory SQLite
TEST_DB_URL='mysql+pymysql://user:pw@127.0.0.1/mavumbi_test?charset=utf8mb4' pytest   # real MySQL/MariaDB (wipes that DB)
```

## Package as an .exe
`pip install pyinstaller && pyinstaller --noconsole --name MavumbiClub main.py`
(ship `.env` next to the executable).

## Standards this codebase holds itself to
1. Money is `DECIMAL(12,2)` / `Decimal`, never float. Rounding is half-up to the cent.
2. Business rules live in `app/rules.py` (pure functions) and `app/services/` (transactions), never in the GUI.
3. One user action = one database transaction (`session_scope`); failure leaves stock and money untouched.
4. The ledger is append-only. Errors are corrected by reversal entries.
5. Income is booked when money is received (fees collected, surcharges paid, sponsorship received), not when owed.
6. Passwords are bcrypt-hashed; every sensitive action is audit-logged; roles gate tabs.
7. Every rule has a test, including boundaries (age 11/12/35/36, discount at exactly 10,000, stock at exactly 20%).

## Layout
```
app/rules.py        pure business rules          app/models.py     schema (SQLAlchemy)
app/services/       membership, store, events, equipment, commercial, ledger, reports, auth
app/ui/             PySide6 screens              manage.py         admin CLI
docs/               ARCHITECTURE.md, ASSUMPTIONS.md, DATA_DICTIONARY.md, schema.sql
```
