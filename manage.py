"""Admin CLI.   python manage.py <command>

  init-db            create all tables (safe to re-run) and load reference data
  create-user        add a login (prompts for password)
  demo-data          load a small demo dataset (members, sales, an event) for trying the app
  schema-sql         write docs/schema.sql (MySQL DDL generated from the models)
  data-dictionary    write docs/DATA_DICTIONARY.md
"""
import argparse
import getpass
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app import db, seed
from app.errors import ClubError
from app.models import Base, Item, Sport
from app.services import auth, commercial, events, football, membership, store


def cmd_init_db(_):
    db.init_db()
    with db.session_scope() as s:
        seed.seed_reference_data(s)
    print("Database ready. Create a login next:  python manage.py create-user admin --role admin")


def cmd_create_user(a):
    pw = getpass.getpass("Password (min 8 chars): ")
    if pw != getpass.getpass("Repeat: "):
        sys.exit("Passwords differ")
    with db.session_scope() as s:
        auth.create_user(s, a.username, pw, a.role)
    print(f"User '{a.username}' ({a.role}) created")


def cmd_demo(_):
    base = dict(phone="0712345678", next_of_kin_name="Parent", next_of_kin_contact="0722345678")
    with db.session_scope() as s:
        people = [("Achieng Otieno", "Female", date(2009, 4, 2), ["Netball", "Football"]),
                  ("Brian Kamau", "Male", date(2001, 8, 19), ["Football", "Rugby"]),
                  ("Cynthia Wanjiru", "Female", date(1996, 1, 30), ["Chess"]),
                  ("David Mutua", "Male", date(2004, 11, 11), ["Football", "Basketball"]),
                  ("Esther Njeri", "Female", date(2007, 6, 6), ["Volleyball"])]
        ms = [membership.register_member(s, full_name=n, gender=g, date_of_birth=d, games=gm, sub_county="Central", **base)
              for n, g, d, gm in people]
        shorts = s.scalar(select(Item).where(Item.name == "Games shorts"))
        store.sell(s, [{"item_id": shorts.id, "qty": 3}], "cash", person_id=ms[0].person_id)
        fb = s.scalar(select(Sport).where(Sport.name == "Football"))
        membership.assign_role(s, ms[1].person_id, "Patron", fb.id)
        ev = events.create_event(s, fb.id, "Friendly vs Kisumu FC", date.today() + timedelta(days=7),
                                 "Mavumbi Grounds", "Kisumu FC", 200)
        events.set_roster(s, ev.id, [ms[1].person_id, ms[3].person_id], ms[3].person_id)
        sp = commercial.add_sponsor(s, "Mavumbi County Bank", "Ms. Akinyi")
        commercial.record_sponsorship(s, sp.id, 50000, purpose="Season kit")
        past = events.create_event(s, fb.id, "League: Mavumbi vs Nyali", date.today() - timedelta(days=14),
                                   "Mavumbi Grounds", "Nyali United")
        events.set_roster(s, past.id, [ms[1].person_id, ms[3].person_id], ms[3].person_id)
        football.record_result(s, past.id, 2, 1, [{"member_id": ms[3].person_id, "minutes": 90, "scored": 2},
                                                 {"member_id": ms[1].person_id, "minutes": 90, "assists": 1}])
        sq = football.create_squad(s, fb.id, "2026/27")
        football.add_to_squad(s, sq.id, ms[3].person_id, 9, "Forward")
        football.add_to_squad(s, sq.id, ms[1].person_id, 6, "Midfielder")
        football.sign_contract(s, ms[3].person_id, fb.id, "amateur", date.today(), date.today() + timedelta(days=60))
    print("Demo data loaded")


def cmd_schema(_):
    ddl = "\n\n".join(str(CreateTable(t).compile(dialect=mysql.dialect())).strip() + ";" for t in Base.metadata.sorted_tables)
    Path("docs").mkdir(exist_ok=True)
    Path("docs/schema.sql").write_text("-- Generated from app/models.py (MySQL 8). Do not edit by hand.\n"
                                       "CREATE DATABASE IF NOT EXISTS mavumbi_club CHARACTER SET utf8mb4;\nUSE mavumbi_club;\n\n" + ddl + "\n")
    print("docs/schema.sql written")


def cmd_dictionary(_):
    out = ["# Data dictionary", "", "Generated from `app/models.py` by `python manage.py data-dictionary`.", ""]
    for t in Base.metadata.sorted_tables:
        out += [f"## `{t.name}`", "", "| Column | Type | Null | Key | Default |", "|---|---|---|---|---|"]
        for c in t.columns:
            key = "PK" if c.primary_key else (f"FK -> {next(iter(c.foreign_keys)).column.table.name}" if c.foreign_keys else
                                              ("UNIQUE" if c.unique else ""))
            dflt = "" if c.default is None and c.server_default is None else "yes"
            out.append(f"| {c.name} | {c.type} | {'yes' if c.nullable else 'no'} | {key} | {dflt} |")
        out.append("")
    Path("docs").mkdir(exist_ok=True)
    Path("docs/DATA_DICTIONARY.md").write_text("\n".join(out))
    print("docs/DATA_DICTIONARY.md written")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db").set_defaults(fn=cmd_init_db)
    cu = sub.add_parser("create-user")
    cu.add_argument("username")
    cu.add_argument("--role", choices=auth.ROLES, required=True)
    cu.set_defaults(fn=cmd_create_user)
    sub.add_parser("demo-data").set_defaults(fn=cmd_demo)
    sub.add_parser("schema-sql").set_defaults(fn=cmd_schema)
    sub.add_parser("data-dictionary").set_defaults(fn=cmd_dictionary)
    a = p.parse_args()
    try:
        a.fn(a)
    except ClubError as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
