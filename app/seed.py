"""Reference data: the 15 games, roles, the store price list, and SAMPLE equipment/merchandise.

Prices for store items come from the case study. Equipment market values and fan-merchandise
prices are SAMPLE values: edit them to real figures before relying on surcharge totals.
"""
from sqlalchemy import select

from .models import Equipment, Item, Role, Sport, StockMovement

SPORTS = ["Swimming", "Hockey", "Lawn tennis", "Table tennis", "Darts", "Badminton", "Volleyball", "Basketball",
          "Netball", "Football", "Baseball", "Rugby", "Pool", "Chess", "Draft"]
ROLES = ["Member", "Captain", "Patron", "Store clerk", "Fan", "Sponsor contact"]
# name, price, (min, max) for variable pricing, max stock
MEMBER_ITEMS = [("Blommer", 250, None, 100), ("Games shorts", 750, None, 100), ("Hockey stick", 2000, None, 50),
                ("Socks", 350, None, 150), ("Sports shoes", 1000, (1000, 4000), 80), ("Track suit", 1000, None, 80),
                ("T-shirt", 800, None, 150), ("Wrapper", 450, None, 100)]
FAN_ITEMS = [("Club jersey", 3500, 200), ("Club scarf", 1200, 200), ("Club cap", 900, 150)]  # SAMPLE prices
EQUIPMENT = [("Hockey stick (club)", "Hockey", 2000, 12), ("Football (match)", "Football", 3000, 10),
             ("Volleyball", "Volleyball", 2500, 6), ("Basketball", "Basketball", 3000, 6),
             ("Netball", "Netball", 2500, 6), ("Rugby ball", "Rugby", 3500, 6), ("Badminton racket", "Badminton", 2500, 8),
             ("Table tennis bat", "Table tennis", 1200, 8), ("Chess set", "Chess", 1500, 6), ("Pool cue", "Pool", 2500, 6),
             ("Tennis racket", "Lawn tennis", 5000, 6), ("Swim goggles", "Swimming", 800, 10),
             ("Baseball bat", "Baseball", 4000, 6), ("Dart set", "Darts", 1000, 6), ("Draft board", "Draft", 1200, 6)]


def seed_reference_data(session) -> None:
    for n in SPORTS:
        if not session.scalar(select(Sport).where(Sport.name == n)):
            session.add(Sport(name=n))
    for n in ROLES:
        if not session.scalar(select(Role).where(Role.name == n)):
            session.add(Role(name=n))
    session.flush()
    for n, price, rng, mx in MEMBER_ITEMS:
        if not session.scalar(select(Item).where(Item.name == n)):
            it = Item(name=n, channel="member", unit_price=price, max_stock=mx, stock_qty=mx,
                      price_min=rng[0] if rng else None, price_max=rng[1] if rng else None)
            session.add(it)
            session.flush()
            session.add(StockMovement(item_id=it.id, change=mx, reason="restock", resulting_qty=mx))
    for n, price, mx in FAN_ITEMS:
        if not session.scalar(select(Item).where(Item.name == n)):
            it = Item(name=n, channel="fan", unit_price=price, max_stock=mx, stock_qty=mx)
            session.add(it)
            session.flush()
            session.add(StockMovement(item_id=it.id, change=mx, reason="restock", resulting_qty=mx))
    for n, sport, val, qty in EQUIPMENT:
        if not session.scalar(select(Equipment).where(Equipment.name == n)):
            sid = session.scalar(select(Sport.id).where(Sport.name == sport))
            session.add(Equipment(name=n, sport_id=sid, market_value=val, qty_total=qty, qty_available=qty))
    session.flush()
