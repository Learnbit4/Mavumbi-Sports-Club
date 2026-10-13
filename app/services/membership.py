from __future__ import annotations

import re
from datetime import date

from sqlalchemy import select

from .. import rules
from ..errors import NotFound, ValidationError
from ..models import Member, MemberSport, OrgGroup, Person, PersonRole, Role, Sport
from . import audit, ledger

PHONE = re.compile(r"^\+?[0-9 ]{9,15}$")
GENDERS = ("Male", "Female", "Other")
ORG_TYPES = ("School", "College", "Religious", "Other")


def list_sports(session) -> list[Sport]:
    return list(session.scalars(select(Sport).order_by(Sport.name)))


def list_groups(session) -> list[OrgGroup]:
    return list(session.scalars(select(OrgGroup).order_by(OrgGroup.name)))


def create_group(session, name: str, org_type: str) -> OrgGroup:
    if not name.strip():
        raise ValidationError("Group name required")
    if org_type not in ORG_TYPES:
        raise ValidationError(f"Group type must be one of {ORG_TYPES}")
    if session.scalar(select(OrgGroup).where(OrgGroup.name == name.strip())):
        raise ValidationError("A group with that name already exists")
    g = OrgGroup(name=name.strip(), org_type=org_type)
    session.add(g)
    session.flush()
    return g


def _sport(session, ref) -> Sport:
    s = session.get(Sport, ref) if isinstance(ref, int) else session.scalar(select(Sport).where(Sport.name == ref))
    if s is None:
        raise NotFound(f"Sport '{ref}' not found")
    return s


def assign_role(session, person_id: int, role_name: str, sport_id: int | None = None) -> None:
    role = session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise NotFound(f"Role '{role_name}' not found")
    exists = session.scalar(select(PersonRole.id).where(
        PersonRole.person_id == person_id, PersonRole.role_id == role.id, PersonRole.sport_id == sport_id))
    if exists is None:
        session.add(PersonRole(person_id=person_id, role_id=role.id, sport_id=sport_id))
    if role_name == "Patron" and sport_id:
        session.get(Sport, sport_id).patron_id = person_id


def register_member(session, *, full_name: str, gender: str, date_of_birth: date, phone: str,
                    next_of_kin_name: str, next_of_kin_contact: str, games: list, sub_county: str = "",
                    institution: str = "", weight_kg=None, height_cm=None, special_needs: str = "",
                    email: str = "", group_id: int | None = None, on: date | None = None,
                    user_id=None) -> Member:
    """Enrol one member. Individual pays Ksh 1,000; a group member pays Ksh 500. Posts to the ledger."""
    on = on or date.today()
    if not full_name.strip():
        raise ValidationError("Full name required")
    if gender not in GENDERS:
        raise ValidationError(f"Gender must be one of {GENDERS}")
    if date_of_birth > on:
        raise ValidationError("Date of birth cannot be in the future")
    age = rules.age_on(date_of_birth, on)
    if not rules.MIN_AGE <= age <= rules.MAX_AGE:
        raise ValidationError(f"Age {age} is outside the enrolment range {rules.MIN_AGE}-{rules.MAX_AGE}")
    for label, num in (("Phone", phone), ("Next of kin contact", next_of_kin_contact)):
        if not PHONE.match(num or ""):
            raise ValidationError(f"{label} number looks invalid")
    if not next_of_kin_name.strip():
        raise ValidationError("Next of kin required")
    if not games:
        raise ValidationError("Choose at least one game of interest")
    sports = [_sport(session, g) for g in games]
    if len({s.id for s in sports}) != len(sports):
        raise ValidationError("A game was listed twice in the priority list")
    if group_id is not None and session.get(OrgGroup, group_id) is None:
        raise NotFound("Group not found")

    person = Person(full_name=full_name.strip(), gender=gender, date_of_birth=date_of_birth,
                    phone=phone, email=email or None, sub_county=sub_county or None)
    session.add(person)
    session.flush()
    fee = rules.membership_fee(is_group=group_id is not None)
    m = Member(person_id=person.id, next_of_kin_name=next_of_kin_name.strip(),
               next_of_kin_contact=next_of_kin_contact, institution=institution or None,
               weight_kg=weight_kg, height_cm=height_cm, special_needs=special_needs or None,
               group_id=group_id, fee_charged=fee, enrolled_on=on)
    session.add(m)
    for i, s in enumerate(sports, start=1):
        session.add(MemberSport(member_id=person.id, sport_id=s.id, priority=i))
    session.flush()
    assign_role(session, person.id, "Member")
    ledger.post(session, "IN", "membership", fee, f"Membership: {person.full_name}", "member", person.id,
                entry_date=on, user_id=user_id)
    audit.log(session, user_id, "member_registered", f"{person.full_name} (#{person.id}) fee {fee}")
    return m


def register_group(session, name: str, org_type: str, members: list[dict], user_id=None):
    """Enrol a whole group at Ksh 500 each, all-or-nothing."""
    if not members:
        raise ValidationError("A group enrolment needs at least one member")
    with session.begin_nested():
        g = create_group(session, name, org_type)
        enrolled = [register_member(session, group_id=g.id, user_id=user_id, **m) for m in members]
    return g, enrolled


def member_category(member: Member, on: date | None = None) -> str:
    return rules.age_category(rules.age_on(member.person.date_of_birth, on), strict=False)
