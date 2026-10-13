import os
from datetime import date

import pytest

from app import db, seed
from app.models import Base
from app.services import membership


@pytest.fixture
def session():
    # Default: in-memory SQLite. Set TEST_DB_URL to run the whole suite against MySQL/MariaDB.
    engine = db.configure(os.getenv("TEST_DB_URL", "sqlite://"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = db.new_session()
    seed.seed_reference_data(s)
    s.commit()
    yield s
    s.close()


@pytest.fixture
def make_member(session):
    n = {"i": 0}

    def _make(**kw):
        n["i"] += 1
        args = dict(full_name=f"Member {n['i']}", gender="Male", date_of_birth=date(2005, 6, 15),
                    phone="0712345678", next_of_kin_name="Parent", next_of_kin_contact="0722345678",
                    games=["Football", "Chess"], sub_county="Central", on=date(2026, 10, 12))
        args.update(kw)
        return membership.register_member(session, **args)
    return _make
