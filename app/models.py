"""SQLAlchemy models = the database schema. One shared Person table, one shared ledger."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint, func)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MONEY = Numeric(12, 2)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- people
class Person(Base):
    """Members, fans, patrons, clerks and sponsor contacts all live here; roles distinguish them."""
    __tablename__ = "person"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    gender: Mapped[str | None] = mapped_column(String(10))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))
    sub_county: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OrgGroup(Base):
    """A school, college or religious organisation enrolling members together."""
    __tablename__ = "org_group"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    org_type: Mapped[str] = mapped_column(String(20))
    __table_args__ = (CheckConstraint("org_type IN ('School','College','Religious','Other')"),)


class Sport(Base):
    __tablename__ = "sport"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    patron_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))


class Role(Base):
    __tablename__ = "role"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40), unique=True)


class PersonRole(Base):
    __tablename__ = "person_role"
    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("role.id"))
    sport_id: Mapped[int | None] = mapped_column(ForeignKey("sport.id"))  # patron/captain of which sport
    __table_args__ = (UniqueConstraint("person_id", "role_id", "sport_id"),)


class Member(Base):
    __tablename__ = "member"
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"), primary_key=True)
    next_of_kin_name: Mapped[str] = mapped_column(String(120))
    next_of_kin_contact: Mapped[str] = mapped_column(String(30))
    institution: Mapped[str | None] = mapped_column(String(120))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    special_needs: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("org_group.id"))
    fee_charged: Mapped[Decimal] = mapped_column(MONEY)
    enrolled_on: Mapped[date] = mapped_column(Date)
    person: Mapped[Person] = relationship()
    group: Mapped[OrgGroup | None] = relationship()


class MemberSport(Base):
    """Games of interest in priority order (1 = first choice)."""
    __tablename__ = "member_sport"
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"), primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sport.id"), primary_key=True)
    priority: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("member_id", "priority"),)


# ---------------------------------------------------------------- store
class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    channel: Mapped[str] = mapped_column(String(10), default="member")  # member | fan
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    price_min: Mapped[Decimal | None] = mapped_column(MONEY)  # set for variable-price items (shoes)
    price_max: Mapped[Decimal | None] = mapped_column(MONEY)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0)
    max_stock: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("stock_qty >= 0"), CheckConstraint("max_stock > 0"),
                      CheckConstraint("channel IN ('member','fan')"))


class Sale(Base):
    __tablename__ = "sale"
    id: Mapped[int] = mapped_column(primary_key=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    channel: Mapped[str] = mapped_column(String(10))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    discount: Mapped[Decimal] = mapped_column(MONEY)
    total: Mapped[Decimal] = mapped_column(MONEY)
    payment_method: Mapped[str] = mapped_column(String(15))
    payment_ref: Mapped[str | None] = mapped_column(String(60))
    served_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    lines: Mapped[list[SaleLine]] = relationship(back_populates="sale")
    __table_args__ = (CheckConstraint("payment_method IN ('cash','mobile_money')"),)


class SaleLine(Base):
    __tablename__ = "sale_line"
    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sale.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    line_total: Mapped[Decimal] = mapped_column(MONEY)
    sale: Mapped[Sale] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()
    __table_args__ = (CheckConstraint("qty > 0"),)


class StockMovement(Base):
    """Every change to stock, with the resulting level: the audit trail for 'subsequent stock levels'."""
    __tablename__ = "stock_movement"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    moved_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    change: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(20))  # sale | restock | adjustment
    ref_id: Mapped[int | None] = mapped_column(Integer)
    resulting_qty: Mapped[int] = mapped_column(Integer)


# ---------------------------------------------------------------- equipment
class Equipment(Base):
    """Club equipment loaned to teams (distinct from items sold in the store)."""
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sport.id"))
    market_value: Mapped[Decimal] = mapped_column(MONEY)
    qty_total: Mapped[int] = mapped_column(Integer)
    qty_available: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("qty_available >= 0 AND qty_available <= qty_total"),)


# ---------------------------------------------------------------- events
class Event(Base):
    __tablename__ = "event"
    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sport.id"))
    title: Mapped[str] = mapped_column(String(120))
    event_date: Mapped[date] = mapped_column(Date, index=True)
    venue: Mapped[str | None] = mapped_column(String(120))
    opponent: Mapped[str | None] = mapped_column(String(120))
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)
    ticket_price: Mapped[Decimal] = mapped_column(MONEY, default=0)
    patron_commission: Mapped[Decimal] = mapped_column(MONEY, default=0)
    commission_posted: Mapped[bool] = mapped_column(Boolean, default=False)


class EventRoster(Base):
    __tablename__ = "event_roster"
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"), primary_key=True)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    fee_amount: Mapped[Decimal] = mapped_column(MONEY, default=0)
    fee_paid_on: Mapped[date | None] = mapped_column(Date)


class EquipmentIssue(Base):
    __tablename__ = "equipment_issue"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"))
    captain_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"))
    issued_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    returned_at: Mapped[datetime | None] = mapped_column(DateTime)
    lines: Mapped[list[EquipmentIssueLine]] = relationship(back_populates="issue")


class EquipmentIssueLine(Base):
    __tablename__ = "equipment_issue_line"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("equipment_issue.id"), index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"))
    qty_out: Mapped[int] = mapped_column(Integer)
    qty_returned: Mapped[int] = mapped_column(Integer, default=0)
    qty_lost: Mapped[int] = mapped_column(Integer, default=0)
    qty_damaged: Mapped[int] = mapped_column(Integer, default=0)
    issue: Mapped[EquipmentIssue] = relationship(back_populates="lines")
    equipment: Mapped[Equipment] = relationship()


class Surcharge(Base):
    """A team member's share of a loss/damage charge. Income is booked only when paid."""
    __tablename__ = "surcharge"
    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("equipment_issue.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    paid_on: Mapped[date | None] = mapped_column(Date)


# ---------------------------------------------------------------- commercial
class TicketSale(Base):
    __tablename__ = "ticket_sale"
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), index=True)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    total: Mapped[Decimal] = mapped_column(MONEY)
    sold_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (CheckConstraint("qty > 0"),)


class Sponsor(Base):
    __tablename__ = "sponsor"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    contact_person: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(120))


class SponsorshipPayment(Base):
    __tablename__ = "sponsorship_payment"
    id: Mapped[int] = mapped_column(primary_key=True)
    sponsor_id: Mapped[int] = mapped_column(ForeignKey("sponsor.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    received_on: Mapped[date] = mapped_column(Date)
    purpose: Mapped[str | None] = mapped_column(String(200))
    sport_id: Mapped[int | None] = mapped_column(ForeignKey("sport.id"))


# ---------------------------------------------------------------- finance / security
class LedgerEntry(Base):
    """Append-only. Every shilling in or out is one row. Mistakes are fixed by reversal, never by edit."""
    __tablename__ = "ledger_entry"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date)
    direction: Mapped[str] = mapped_column(String(3))
    category: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    description: Mapped[str | None] = mapped_column(String(255))
    ref_type: Mapped[str | None] = mapped_column(String(30))
    ref_id: Mapped[int | None] = mapped_column(Integer)
    reversal_of: Mapped[int | None] = mapped_column(ForeignKey("ledger_entry.id"), unique=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    __table_args__ = (CheckConstraint("direction IN ('IN','OUT')"), CheckConstraint("amount > 0"),
                      Index("ix_ledger_cat_date", "category", "entry_date"))


class User(Base):
    __tablename__ = "app_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(10))
    person_id: Mapped[int | None] = mapped_column(ForeignKey("person.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (CheckConstraint("role IN ('admin','manager','clerk','patron')"),)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("app_user.id"))
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str | None] = mapped_column(String(500))


# ---------------------------------------------------------------- football operations
class Squad(Base):
    """A sport's squad for one season. Players are existing Members (no separate player table)."""
    __tablename__ = "squad"
    id: Mapped[int] = mapped_column(primary_key=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sport.id"))
    season: Mapped[str] = mapped_column(String(9))
    __table_args__ = (UniqueConstraint("sport_id", "season"),)


class SquadPlayer(Base):
    __tablename__ = "squad_player"
    squad_id: Mapped[int] = mapped_column(ForeignKey("squad.id"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"), primary_key=True)
    shirt_number: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[str | None] = mapped_column(String(30))
    joined_on: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("squad_id", "shirt_number"),)


class Contract(Base):
    __tablename__ = "contract"
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"), index=True)
    sport_id: Mapped[int] = mapped_column(ForeignKey("sport.id"))
    contract_type: Mapped[str] = mapped_column(String(12))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    monthly_wage: Mapped[Decimal] = mapped_column(MONEY, default=0)
    terminated_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(255))
    __table_args__ = (CheckConstraint("contract_type IN ('amateur','youth','professional')"),
                      CheckConstraint("end_date > start_date"), CheckConstraint("monthly_wage >= 0"))


class WagePayment(Base):
    __tablename__ = "wage_payment"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contract.id"), index=True)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    amount: Mapped[Decimal] = mapped_column(MONEY)
    paid_on: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("contract_id", "period"),)


class Injury(Base):
    __tablename__ = "injury"
    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    injured_on: Mapped[date] = mapped_column(Date)
    expected_return: Mapped[date | None] = mapped_column(Date)
    cleared_on: Mapped[date | None] = mapped_column(Date)


class MatchResult(Base):
    """Club score vs opponent for an external fixture (one result per event)."""
    __tablename__ = "match_result"
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), primary_key=True)
    score_for: Mapped[int] = mapped_column(Integer)
    score_against: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("score_for >= 0 AND score_against >= 0"),)


class PlayerMatchStat(Base):
    __tablename__ = "player_match_stat"
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id"), primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("member.person_id"), primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    scored: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("minutes BETWEEN 0 AND 240 AND scored >= 0 AND assists >= 0 "
                                      "AND yellow_cards BETWEEN 0 AND 2 AND red_cards BETWEEN 0 AND 1"),)
