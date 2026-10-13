# Data dictionary

Generated from `app/models.py` by `python manage.py data-dictionary`.

## `item`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| name | VARCHAR(80) | no | UNIQUE |  |
| channel | VARCHAR(10) | no |  | yes |
| unit_price | NUMERIC(12, 2) | no |  |  |
| price_min | NUMERIC(12, 2) | yes |  |  |
| price_max | NUMERIC(12, 2) | yes |  |  |
| stock_qty | INTEGER | no |  | yes |
| max_stock | INTEGER | no |  |  |
| active | BOOLEAN | no |  | yes |

## `org_group`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| name | VARCHAR(120) | no | UNIQUE |  |
| org_type | VARCHAR(20) | no |  |  |

## `person`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| full_name | VARCHAR(120) | no |  |  |
| gender | VARCHAR(10) | yes |  |  |
| date_of_birth | DATE | yes |  |  |
| phone | VARCHAR(30) | yes |  |  |
| email | VARCHAR(120) | yes |  |  |
| sub_county | VARCHAR(80) | yes |  |  |
| created_at | DATETIME | no |  | yes |

## `role`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| name | VARCHAR(40) | no | UNIQUE |  |

## `sponsor`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| name | VARCHAR(120) | no | UNIQUE |  |
| contact_person | VARCHAR(120) | yes |  |  |
| phone | VARCHAR(30) | yes |  |  |
| email | VARCHAR(120) | yes |  |  |

## `app_user`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| username | VARCHAR(40) | no | UNIQUE |  |
| password_hash | VARCHAR(100) | no |  |  |
| role | VARCHAR(10) | no |  |  |
| person_id | INTEGER | yes | FK -> person |  |
| active | BOOLEAN | no |  | yes |

## `member`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| person_id | INTEGER | no | PK |  |
| next_of_kin_name | VARCHAR(120) | no |  |  |
| next_of_kin_contact | VARCHAR(30) | no |  |  |
| institution | VARCHAR(120) | yes |  |  |
| weight_kg | NUMERIC(5, 1) | yes |  |  |
| height_cm | NUMERIC(5, 1) | yes |  |  |
| special_needs | TEXT | yes |  |  |
| group_id | INTEGER | yes | FK -> org_group |  |
| fee_charged | NUMERIC(12, 2) | no |  |  |
| enrolled_on | DATE | no |  |  |

## `sport`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| name | VARCHAR(60) | no | UNIQUE |  |
| patron_id | INTEGER | yes | FK -> person |  |

## `stock_movement`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| item_id | INTEGER | no | FK -> item |  |
| moved_at | DATETIME | no |  | yes |
| change | INTEGER | no |  |  |
| reason | VARCHAR(20) | no |  |  |
| ref_id | INTEGER | yes |  |  |
| resulting_qty | INTEGER | no |  |  |

## `audit_log`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| at | DATETIME | no |  | yes |
| user_id | INTEGER | yes | FK -> app_user |  |
| action | VARCHAR(40) | no |  |  |
| detail | VARCHAR(500) | yes |  |  |

## `contract`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| member_id | INTEGER | no | FK -> member |  |
| sport_id | INTEGER | no | FK -> sport |  |
| contract_type | VARCHAR(12) | no |  |  |
| start_date | DATE | no |  |  |
| end_date | DATE | no |  |  |
| monthly_wage | NUMERIC(12, 2) | no |  | yes |
| terminated_on | DATE | yes |  |  |
| notes | VARCHAR(255) | yes |  |  |

## `equipment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| name | VARCHAR(80) | no | UNIQUE |  |
| sport_id | INTEGER | no | FK -> sport |  |
| market_value | NUMERIC(12, 2) | no |  |  |
| qty_total | INTEGER | no |  |  |
| qty_available | INTEGER | no |  |  |

## `event`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| sport_id | INTEGER | no | FK -> sport |  |
| title | VARCHAR(120) | no |  |  |
| event_date | DATE | no |  |  |
| venue | VARCHAR(120) | yes |  |  |
| opponent | VARCHAR(120) | yes |  |  |
| is_external | BOOLEAN | no |  | yes |
| ticket_price | NUMERIC(12, 2) | no |  | yes |
| patron_commission | NUMERIC(12, 2) | no |  | yes |
| commission_posted | BOOLEAN | no |  | yes |

## `injury`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| member_id | INTEGER | no | FK -> member |  |
| description | VARCHAR(200) | no |  |  |
| injured_on | DATE | no |  |  |
| expected_return | DATE | yes |  |  |
| cleared_on | DATE | yes |  |  |

## `ledger_entry`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| entry_date | DATE | no |  |  |
| direction | VARCHAR(3) | no |  |  |
| category | VARCHAR(30) | no |  |  |
| amount | NUMERIC(12, 2) | no |  |  |
| description | VARCHAR(255) | yes |  |  |
| ref_type | VARCHAR(30) | yes |  |  |
| ref_id | INTEGER | yes |  |  |
| reversal_of | INTEGER | yes | FK -> ledger_entry |  |
| created_by | INTEGER | yes | FK -> app_user |  |
| created_at | DATETIME | no |  | yes |

## `member_sport`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| member_id | INTEGER | no | PK |  |
| sport_id | INTEGER | no | PK |  |
| priority | INTEGER | no |  |  |

## `person_role`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| person_id | INTEGER | no | FK -> person |  |
| role_id | INTEGER | no | FK -> role |  |
| sport_id | INTEGER | yes | FK -> sport |  |

## `sale`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| sold_at | DATETIME | no |  | yes |
| channel | VARCHAR(10) | no |  |  |
| person_id | INTEGER | yes | FK -> person |  |
| subtotal | NUMERIC(12, 2) | no |  |  |
| discount | NUMERIC(12, 2) | no |  |  |
| total | NUMERIC(12, 2) | no |  |  |
| payment_method | VARCHAR(15) | no |  |  |
| payment_ref | VARCHAR(60) | yes |  |  |
| served_by | INTEGER | yes | FK -> app_user |  |

## `sponsorship_payment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| sponsor_id | INTEGER | no | FK -> sponsor |  |
| amount | NUMERIC(12, 2) | no |  |  |
| received_on | DATE | no |  |  |
| purpose | VARCHAR(200) | yes |  |  |
| sport_id | INTEGER | yes | FK -> sport |  |

## `squad`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| sport_id | INTEGER | no | FK -> sport |  |
| season | VARCHAR(9) | no |  |  |

## `equipment_issue`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| event_id | INTEGER | no | FK -> event |  |
| captain_id | INTEGER | no | FK -> member |  |
| issued_at | DATETIME | no |  | yes |
| returned_at | DATETIME | yes |  |  |

## `event_roster`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| event_id | INTEGER | no | PK |  |
| member_id | INTEGER | no | PK |  |
| is_captain | BOOLEAN | no |  | yes |
| fee_amount | NUMERIC(12, 2) | no |  | yes |
| fee_paid_on | DATE | yes |  |  |

## `match_result`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| event_id | INTEGER | no | PK |  |
| score_for | INTEGER | no |  |  |
| score_against | INTEGER | no |  |  |

## `player_match_stat`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| event_id | INTEGER | no | PK |  |
| member_id | INTEGER | no | PK |  |
| minutes | INTEGER | no |  | yes |
| scored | INTEGER | no |  | yes |
| assists | INTEGER | no |  | yes |
| yellow_cards | INTEGER | no |  | yes |
| red_cards | INTEGER | no |  | yes |

## `sale_line`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| sale_id | INTEGER | no | FK -> sale |  |
| item_id | INTEGER | no | FK -> item |  |
| qty | INTEGER | no |  |  |
| unit_price | NUMERIC(12, 2) | no |  |  |
| line_total | NUMERIC(12, 2) | no |  |  |

## `squad_player`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| squad_id | INTEGER | no | PK |  |
| member_id | INTEGER | no | PK |  |
| shirt_number | INTEGER | yes |  |  |
| position | VARCHAR(30) | yes |  |  |
| joined_on | DATE | no |  |  |

## `ticket_sale`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| event_id | INTEGER | no | FK -> event |  |
| person_id | INTEGER | yes | FK -> person |  |
| qty | INTEGER | no |  |  |
| unit_price | NUMERIC(12, 2) | no |  |  |
| total | NUMERIC(12, 2) | no |  |  |
| sold_at | DATETIME | no |  | yes |

## `wage_payment`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| contract_id | INTEGER | no | FK -> contract |  |
| period | VARCHAR(7) | no |  |  |
| amount | NUMERIC(12, 2) | no |  |  |
| paid_on | DATE | no |  |  |

## `equipment_issue_line`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| issue_id | INTEGER | no | FK -> equipment_issue |  |
| equipment_id | INTEGER | no | FK -> equipment |  |
| qty_out | INTEGER | no |  |  |
| qty_returned | INTEGER | no |  | yes |
| qty_lost | INTEGER | no |  | yes |
| qty_damaged | INTEGER | no |  | yes |

## `surcharge`

| Column | Type | Null | Key | Default |
|---|---|---|---|---|
| id | INTEGER | no | PK |  |
| issue_id | INTEGER | no | FK -> equipment_issue |  |
| member_id | INTEGER | no | FK -> member |  |
| amount | NUMERIC(12, 2) | no |  |  |
| paid_on | DATE | yes |  |  |
