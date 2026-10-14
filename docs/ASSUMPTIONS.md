# Assumptions and design decisions

The case study is silent or ambiguous on these points. Each is a decision; change it in one place if wrong.

| # | Gap | Decision | Where |
|---|---|---|---|
| 1 | Equipment loaned to teams is not in the store price list | Separate `equipment` table with sport, market value, quantities. **Market values are SAMPLE figures:  | `seed.py` |
| 2 | "Total income" undefined | Gross = membership + store sales + merchandise + facilitation + surcharges + tickets + sponsorship. Net = gross minus patron commission | `ledger.summary` |
| 3 | Fan, jersey, ticket and sponsor income  | Added as extra ledger categories. Fan merchandise prices are SAMPLE values | `store`, `events`, `commercial` |
| 4 | Surcharge split rule | Equal split across the event's whole team including the captain; leftover cents go to the captain | `rules.split_evenly` |
| 5 | Lost vs damaged equipment | Both are written off the club's quantity and both are surcharged at market value + 10% | `equipment.return_issue` |
| 6 | Surcharge income timing | Booked when the member pays, not when charged | `equipment.pay_surcharge` |
| 7 | Commission base | 20% of facilitation fees **collected** (not merely owed), posted once at settlement, as an expense | `events.settle_event` |
| 8 | Facilitation fee | Ksh 500 per team member, external fixtures only; roster locks once any fee is collected | `events.set_roster` |
| 9 | Age category after enrolment | Derived from date of birth at report time, never stored; members who later pass 35 show as "Over-age" | `rules.age_category` |
| 10 | Discount | 5% only when the purchase **exceeds** Ksh 10,000 (exactly 10,000 gets none), applied per sale | `rules.purchase_totals` |
| 11 | Stock alert | Fires when stock is at or below 20% of the item's max stock level | `rules.needs_reorder` |
| 12 | Shoes (Ksh 1,000-4,000) | Item carries a min/max; the price is entered at sale and validated inside the range | `store.sell` |
| 13 | Channels | A sale is either member store (needs a registered member) or fan merchandise (walk-ins allowed); no mixed carts | `store.sell` |
| 14 | Who may collect equipment | Only the captain of that event | `equipment.issue` |
| 15 | Group enrolment | Each person is a full member record, flagged with the group; fee Ksh 500 each; the group is created and filled all-or-nothing | `membership.register_group` |
| 16 | Payment | Cash or mobile money; mobile money requires a transaction reference | `store.sell` |
| 17 | Are players a new kind of person? | No. A player is an existing Member; squads, contracts and stats reference the member | `models.Squad` etc. |
| 18 | Wages | Only professional/youth contracts carry a wage; amateur wage must be 0; professional must be > 0. A full month's wage is paid per calendar month in the contract (no pro-rating). Posted as an OUT `wages` ledger entry, once per contract per month | `football.pay_wage` |
| 19 | Who pays wages | Only roles with finance rights (admin, manager), enforced in the service, not just the screen | `football.pay_wage` |
| 20 | Contracts | One contract per member at a time (no overlaps, termination frees the slot). **No age rule on contracts**: decide whether minors may sign professional deals | `football.sign_contract` |
| 21 | Match results | Recorded only for external fixtures, only on/after match day, once per event. Players' individual scoring may not exceed the team score (own goals are not modelled) | `football.record_result` |
| 22 | Injuries | An open injury (not cleared on the event date) blocks selection for that event | `events.set_roster` |
| 23 | League points | 3 for a win, 1 for a draw, labelled "Pts (3-1-0)". Other sports may score differently | `rules.league_points` |
| 24 | Squad membership | Not enforced against a member's 3 chosen games or against contracts; a squad is an organising list | `football.add_to_squad` |



