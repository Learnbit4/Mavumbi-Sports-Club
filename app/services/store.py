from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select

from .. import rules
from ..errors import NotFound, StockError, ValidationError
from ..models import Item, Member, Sale, SaleLine, StockMovement
from . import audit, ledger

PAYMENT_METHODS = ("cash", "mobile_money")
CHANNELS = ("member", "fan")


@dataclass
class SaleResult:
    sale: Sale
    alerts: list[Item] = field(default_factory=list)  # items now at/below 20% of max stock


def list_items(session, channel: str | None = None) -> list[Item]:
    q = select(Item).where(Item.active.is_(True)).order_by(Item.name)
    if channel:
        q = q.where(Item.channel == channel)
    return list(session.scalars(q))


def low_stock(session) -> list[Item]:
    return [i for i in list_items(session) if rules.needs_reorder(i.stock_qty, i.max_stock)]


def add_item(session, name: str, unit_price, max_stock: int, channel: str = "member", stock_qty: int = 0,
             price_min=None, price_max=None) -> Item:
    if channel not in CHANNELS:
        raise ValidationError("Invalid channel")
    if max_stock <= 0 or not 0 <= stock_qty <= max_stock:
        raise ValidationError("Stock must be between 0 and the max stock level")
    it = Item(name=name.strip(), channel=channel, unit_price=rules.money(unit_price), max_stock=max_stock,
              stock_qty=stock_qty, price_min=None if price_min is None else rules.money(price_min),
              price_max=None if price_max is None else rules.money(price_max))
    session.add(it)
    session.flush()
    if stock_qty:
        session.add(StockMovement(item_id=it.id, change=stock_qty, reason="restock", resulting_qty=stock_qty))
    return it


def restock(session, item_id: int, qty: int, user_id=None) -> Item:
    it = session.get(Item, item_id, with_for_update=True)
    if it is None:
        raise NotFound("Item not found")
    if qty <= 0:
        raise ValidationError("Restock quantity must be positive")
    if it.stock_qty + qty > it.max_stock:
        raise ValidationError(f"Restock would exceed max stock level ({it.max_stock})")
    it.stock_qty += qty
    session.add(StockMovement(item_id=it.id, change=qty, reason="restock", resulting_qty=it.stock_qty))
    audit.log(session, user_id, "restock", f"{it.name} +{qty}")
    return it


def sell(session, lines: list[dict], payment_method: str, channel: str = "member", person_id: int | None = None,
         payment_ref: str | None = None, user_id=None) -> SaleResult:
    """lines: [{'item_id', 'qty', 'unit_price' (only for variable-price items)}].

    Sale, sale lines, stock decrement, stock history and ledger entry are one transaction
    (the caller's session_scope): any failure leaves stock and money untouched.
    """
    if not lines:
        raise ValidationError("Cart is empty")
    if payment_method not in PAYMENT_METHODS:
        raise ValidationError(f"Payment method must be one of {PAYMENT_METHODS}")
    if payment_method == "mobile_money" and not (payment_ref or "").strip():
        raise ValidationError("Mobile money payments need a transaction reference")
    if channel not in CHANNELS:
        raise ValidationError("Invalid channel")
    if channel == "member" and (person_id is None or session.get(Member, person_id) is None):
        raise ValidationError("Member store sales require a registered member")

    items: dict[int, Item] = {}
    need: dict[int, int] = {}
    priced: list[tuple[Item, int, Decimal]] = []
    for ln in lines:
        qty = int(ln["qty"])
        if qty <= 0:
            raise ValidationError("Quantity must be positive")
        it = items.get(ln["item_id"]) or session.get(Item, ln["item_id"], with_for_update=True)
        if it is None or not it.active:
            raise NotFound("Item not found")
        items[it.id] = it
        if it.channel != channel:
            raise ValidationError(f"'{it.name}' is not sold through the {channel} channel")
        price = it.unit_price
        if it.price_min is not None:
            price = rules.money(ln.get("unit_price") or it.unit_price)
            if not it.price_min <= price <= it.price_max:
                raise ValidationError(f"{it.name} must be priced between {it.price_min} and {it.price_max}")
        need[it.id] = need.get(it.id, 0) + qty
        priced.append((it, qty, price))
    for iid, n in need.items():
        if items[iid].stock_qty < n:
            raise StockError(f"Only {items[iid].stock_qty} of '{items[iid].name}' in stock (asked for {n})")

    subtotal, discount, total = rules.purchase_totals([(q, p) for _, q, p in priced])
    sale = Sale(channel=channel, person_id=person_id, subtotal=subtotal, discount=discount, total=total,
                payment_method=payment_method, payment_ref=payment_ref, served_by=user_id)
    session.add(sale)
    session.flush()
    for it, qty, price in priced:
        session.add(SaleLine(sale_id=sale.id, item_id=it.id, qty=qty, unit_price=price,
                             line_total=rules.money(price * qty)))
    for iid, n in need.items():
        it = items[iid]
        it.stock_qty -= n
        session.add(StockMovement(item_id=iid, change=-n, reason="sale", ref_id=sale.id, resulting_qty=it.stock_qty))
    ledger.post(session, "IN", "store_sale" if channel == "member" else "merchandise", total,
                f"Sale #{sale.id}", "sale", sale.id, user_id=user_id)
    audit.log(session, user_id, "sale", f"#{sale.id} total {total}")
    return SaleResult(sale, [i for i in items.values() if rules.needs_reorder(i.stock_qty, i.max_stock)])
