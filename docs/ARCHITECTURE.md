# Architecture

```
PySide6 screens (app/ui)      thin: collect input, call a service, show the result or the error
        |
Services (app/services)       one function = one business action = one transaction
        |        \
Rules (app/rules.py)    Models (app/models.py)  ->  MySQL
```
`ClubError` subclasses are expected rule violations (shown as warnings). Anything else is logged to
`mavumbi.log` and shown as an "unexpected error: nothing was saved" box.

## Entity relationships
```mermaid
erDiagram
  PERSON ||--o| MEMBER : "is"
  PERSON ||--o{ PERSON_ROLE : has
  ROLE ||--o{ PERSON_ROLE : defines
  SPORT ||--o{ PERSON_ROLE : "patron/captain of"
  ORG_GROUP ||--o{ MEMBER : enrols
  MEMBER ||--o{ MEMBER_SPORT : "ranks games"
  SPORT ||--o{ MEMBER_SPORT : ""
  SPORT ||--o{ EVENT : hosts
  EVENT ||--o{ EVENT_ROSTER : team
  MEMBER ||--o{ EVENT_ROSTER : plays
  EVENT ||--o{ TICKET_SALE : ""
  EVENT ||--o{ EQUIPMENT_ISSUE : ""
  MEMBER ||--o{ EQUIPMENT_ISSUE : "captain collects"
  EQUIPMENT_ISSUE ||--o{ EQUIPMENT_ISSUE_LINE : ""
  EQUIPMENT ||--o{ EQUIPMENT_ISSUE_LINE : ""
  SPORT ||--o{ EQUIPMENT : ""
  EQUIPMENT_ISSUE ||--o{ SURCHARGE : "charges"
  MEMBER ||--o{ SURCHARGE : owes
  ITEM ||--o{ SALE_LINE : ""
  SALE ||--o{ SALE_LINE : ""
  ITEM ||--o{ STOCK_MOVEMENT : ""
  PERSON ||--o{ SALE : buys
  SPONSOR ||--o{ SPONSORSHIP_PAYMENT : pays
  APP_USER ||--o{ AUDIT_LOG : ""
  SPORT ||--o{ SQUAD : ""
  SQUAD ||--o{ SQUAD_PLAYER : ""
  MEMBER ||--o{ SQUAD_PLAYER : ""
  MEMBER ||--o{ CONTRACT : signs
  CONTRACT ||--o{ WAGE_PAYMENT : ""
  MEMBER ||--o{ INJURY : ""
  EVENT ||--o| MATCH_RESULT : ""
  EVENT ||--o{ PLAYER_MATCH_STAT : ""
  MEMBER ||--o{ PLAYER_MATCH_STAT : ""
  LEDGER_ENTRY }o--|| LEDGER_ENTRY : "reversal_of"
```
Every money-moving service writes exactly one `ledger_entry` per cash event, in the same transaction.
Full column list: `DATA_DICTIONARY.md`. MySQL DDL: `schema.sql` (regenerate with `python manage.py schema-sql`).

## Ledger categories
IN: membership, store_sale, merchandise, facilitation, surcharge, ticket, sponsorship. OUT: patron_commission, wages.
A reversal posts the opposite direction in the same category, so category totals net off automatically.
