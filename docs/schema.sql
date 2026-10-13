-- Generated from app/models.py (MySQL 8). Do not edit by hand.
CREATE DATABASE IF NOT EXISTS mavumbi_club CHARACTER SET utf8mb4;
USE mavumbi_club;

CREATE TABLE item (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(80) NOT NULL, 
	channel VARCHAR(10) NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	price_min NUMERIC(12, 2), 
	price_max NUMERIC(12, 2), 
	stock_qty INTEGER NOT NULL, 
	max_stock INTEGER NOT NULL, 
	active BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (stock_qty >= 0), 
	CHECK (max_stock > 0), 
	CHECK (channel IN ('member','fan')), 
	UNIQUE (name)
);

CREATE TABLE org_group (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	org_type VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (org_type IN ('School','College','Religious','Other')), 
	UNIQUE (name)
);

CREATE TABLE person (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	full_name VARCHAR(120) NOT NULL, 
	gender VARCHAR(10), 
	date_of_birth DATE, 
	phone VARCHAR(30), 
	email VARCHAR(120), 
	sub_county VARCHAR(80), 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id)
);

CREATE TABLE `role` (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(40) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE sponsor (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(120) NOT NULL, 
	contact_person VARCHAR(120), 
	phone VARCHAR(30), 
	email VARCHAR(120), 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE app_user (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	username VARCHAR(40) NOT NULL, 
	password_hash VARCHAR(100) NOT NULL, 
	`role` VARCHAR(10) NOT NULL, 
	person_id INTEGER, 
	active BOOL NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (role IN ('admin','manager','clerk','patron')), 
	UNIQUE (username), 
	FOREIGN KEY(person_id) REFERENCES person (id)
);

CREATE TABLE `member` (
	person_id INTEGER NOT NULL, 
	next_of_kin_name VARCHAR(120) NOT NULL, 
	next_of_kin_contact VARCHAR(30) NOT NULL, 
	institution VARCHAR(120), 
	weight_kg NUMERIC(5, 1), 
	height_cm NUMERIC(5, 1), 
	special_needs TEXT, 
	group_id INTEGER, 
	fee_charged NUMERIC(12, 2) NOT NULL, 
	enrolled_on DATE NOT NULL, 
	PRIMARY KEY (person_id), 
	FOREIGN KEY(person_id) REFERENCES person (id), 
	FOREIGN KEY(group_id) REFERENCES org_group (id)
);

CREATE TABLE sport (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(60) NOT NULL, 
	patron_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (name), 
	FOREIGN KEY(patron_id) REFERENCES person (id)
);

CREATE TABLE stock_movement (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	item_id INTEGER NOT NULL, 
	moved_at DATETIME NOT NULL DEFAULT (now()), 
	`change` INTEGER NOT NULL, 
	reason VARCHAR(20) NOT NULL, 
	ref_id INTEGER, 
	resulting_qty INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(item_id) REFERENCES item (id)
);

CREATE TABLE audit_log (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	at DATETIME NOT NULL DEFAULT (now()), 
	user_id INTEGER, 
	action VARCHAR(40) NOT NULL, 
	detail VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES app_user (id)
);

CREATE TABLE contract (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	member_id INTEGER NOT NULL, 
	sport_id INTEGER NOT NULL, 
	contract_type VARCHAR(12) NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	monthly_wage NUMERIC(12, 2) NOT NULL, 
	terminated_on DATE, 
	notes VARCHAR(255), 
	PRIMARY KEY (id), 
	CHECK (contract_type IN ('amateur','youth','professional')), 
	CHECK (end_date > start_date), 
	CHECK (monthly_wage >= 0), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE equipment (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	name VARCHAR(80) NOT NULL, 
	sport_id INTEGER NOT NULL, 
	market_value NUMERIC(12, 2) NOT NULL, 
	qty_total INTEGER NOT NULL, 
	qty_available INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (qty_available >= 0 AND qty_available <= qty_total), 
	UNIQUE (name), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE event (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sport_id INTEGER NOT NULL, 
	title VARCHAR(120) NOT NULL, 
	event_date DATE NOT NULL, 
	venue VARCHAR(120), 
	opponent VARCHAR(120), 
	is_external BOOL NOT NULL, 
	ticket_price NUMERIC(12, 2) NOT NULL, 
	patron_commission NUMERIC(12, 2) NOT NULL, 
	commission_posted BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE injury (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	member_id INTEGER NOT NULL, 
	description VARCHAR(200) NOT NULL, 
	injured_on DATE NOT NULL, 
	expected_return DATE, 
	cleared_on DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id)
);

CREATE TABLE ledger_entry (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	entry_date DATE NOT NULL, 
	direction VARCHAR(3) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	description VARCHAR(255), 
	ref_type VARCHAR(30), 
	ref_id INTEGER, 
	reversal_of INTEGER, 
	created_by INTEGER, 
	created_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	CHECK (direction IN ('IN','OUT')), 
	CHECK (amount > 0), 
	UNIQUE (reversal_of), 
	FOREIGN KEY(reversal_of) REFERENCES ledger_entry (id), 
	FOREIGN KEY(created_by) REFERENCES app_user (id)
);

CREATE TABLE member_sport (
	member_id INTEGER NOT NULL, 
	sport_id INTEGER NOT NULL, 
	priority INTEGER NOT NULL, 
	PRIMARY KEY (member_id, sport_id), 
	UNIQUE (member_id, priority), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE person_role (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	person_id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	sport_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (person_id, role_id, sport_id), 
	FOREIGN KEY(person_id) REFERENCES person (id), 
	FOREIGN KEY(role_id) REFERENCES `role` (id), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE sale (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sold_at DATETIME NOT NULL DEFAULT (now()), 
	channel VARCHAR(10) NOT NULL, 
	person_id INTEGER, 
	subtotal NUMERIC(12, 2) NOT NULL, 
	discount NUMERIC(12, 2) NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	payment_method VARCHAR(15) NOT NULL, 
	payment_ref VARCHAR(60), 
	served_by INTEGER, 
	PRIMARY KEY (id), 
	CHECK (payment_method IN ('cash','mobile_money')), 
	FOREIGN KEY(person_id) REFERENCES person (id), 
	FOREIGN KEY(served_by) REFERENCES app_user (id)
);

CREATE TABLE sponsorship_payment (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sponsor_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	received_on DATE NOT NULL, 
	purpose VARCHAR(200), 
	sport_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(sponsor_id) REFERENCES sponsor (id), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE squad (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sport_id INTEGER NOT NULL, 
	season VARCHAR(9) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (sport_id, season), 
	FOREIGN KEY(sport_id) REFERENCES sport (id)
);

CREATE TABLE equipment_issue (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	event_id INTEGER NOT NULL, 
	captain_id INTEGER NOT NULL, 
	issued_at DATETIME NOT NULL DEFAULT (now()), 
	returned_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES event (id), 
	FOREIGN KEY(captain_id) REFERENCES `member` (person_id)
);

CREATE TABLE event_roster (
	event_id INTEGER NOT NULL, 
	member_id INTEGER NOT NULL, 
	is_captain BOOL NOT NULL, 
	fee_amount NUMERIC(12, 2) NOT NULL, 
	fee_paid_on DATE, 
	PRIMARY KEY (event_id, member_id), 
	FOREIGN KEY(event_id) REFERENCES event (id), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id)
);

CREATE TABLE match_result (
	event_id INTEGER NOT NULL, 
	score_for INTEGER NOT NULL, 
	score_against INTEGER NOT NULL, 
	PRIMARY KEY (event_id), 
	CHECK (score_for >= 0 AND score_against >= 0), 
	FOREIGN KEY(event_id) REFERENCES event (id)
);

CREATE TABLE player_match_stat (
	event_id INTEGER NOT NULL, 
	member_id INTEGER NOT NULL, 
	minutes INTEGER NOT NULL, 
	scored INTEGER NOT NULL, 
	assists INTEGER NOT NULL, 
	yellow_cards INTEGER NOT NULL, 
	red_cards INTEGER NOT NULL, 
	PRIMARY KEY (event_id, member_id), 
	CHECK (minutes BETWEEN 0 AND 240 AND scored >= 0 AND assists >= 0 AND yellow_cards BETWEEN 0 AND 2 AND red_cards BETWEEN 0 AND 1), 
	FOREIGN KEY(event_id) REFERENCES event (id), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id)
);

CREATE TABLE sale_line (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	sale_id INTEGER NOT NULL, 
	item_id INTEGER NOT NULL, 
	qty INTEGER NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	line_total NUMERIC(12, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (qty > 0), 
	FOREIGN KEY(sale_id) REFERENCES sale (id), 
	FOREIGN KEY(item_id) REFERENCES item (id)
);

CREATE TABLE squad_player (
	squad_id INTEGER NOT NULL, 
	member_id INTEGER NOT NULL, 
	shirt_number INTEGER, 
	position VARCHAR(30), 
	joined_on DATE NOT NULL, 
	PRIMARY KEY (squad_id, member_id), 
	UNIQUE (squad_id, shirt_number), 
	FOREIGN KEY(squad_id) REFERENCES squad (id), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id)
);

CREATE TABLE ticket_sale (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	event_id INTEGER NOT NULL, 
	person_id INTEGER, 
	qty INTEGER NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	total NUMERIC(12, 2) NOT NULL, 
	sold_at DATETIME NOT NULL DEFAULT (now()), 
	PRIMARY KEY (id), 
	CHECK (qty > 0), 
	FOREIGN KEY(event_id) REFERENCES event (id), 
	FOREIGN KEY(person_id) REFERENCES person (id)
);

CREATE TABLE wage_payment (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	contract_id INTEGER NOT NULL, 
	period VARCHAR(7) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	paid_on DATE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (contract_id, period), 
	FOREIGN KEY(contract_id) REFERENCES contract (id)
);

CREATE TABLE equipment_issue_line (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	issue_id INTEGER NOT NULL, 
	equipment_id INTEGER NOT NULL, 
	qty_out INTEGER NOT NULL, 
	qty_returned INTEGER NOT NULL, 
	qty_lost INTEGER NOT NULL, 
	qty_damaged INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(issue_id) REFERENCES equipment_issue (id), 
	FOREIGN KEY(equipment_id) REFERENCES equipment (id)
);

CREATE TABLE surcharge (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	issue_id INTEGER NOT NULL, 
	member_id INTEGER NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	paid_on DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(issue_id) REFERENCES equipment_issue (id), 
	FOREIGN KEY(member_id) REFERENCES `member` (person_id)
);
