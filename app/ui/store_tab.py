from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QVBoxLayout, QWidget)

from .. import rules
from ..db import session_scope
from ..models import Member, Person
from ..services import reports, store
from sqlalchemy import select
from .widgets import DataTable, guarded, need_selection


class StoreTab(QWidget):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.cart: list[dict] = []
        self.items: dict[int, object] = {}
        self.channel, self.customer, self.item = QComboBox(), QComboBox(), QComboBox()
        self.channel.addItem("Member store", "member")
        self.channel.addItem("Fan merchandise", "fan")
        self.qty = QSpinBox()
        self.qty.setRange(1, 1000)
        self.price = QDoubleSpinBox()
        self.price.setRange(0, 100000)
        self.price.setEnabled(False)
        self.pay, self.ref = QComboBox(), QLineEdit()
        self.pay.addItems(store.PAYMENT_METHODS)
        self.ref.setPlaceholderText("M-Pesa code (mobile money only)")
        self.totals = QLabel("")
        self.alert = QLabel("")
        self.alert.setStyleSheet("color:#b00020;font-weight:bold")
        self.cart_table, self.stock_table = DataTable(), DataTable()
        add, clear, checkout, restock = (QPushButton(t) for t in ("Add to cart", "Clear cart", "Checkout", "Restock selected…"))
        add.clicked.connect(self._add)
        clear.clicked.connect(self._clear)
        checkout.clicked.connect(self._checkout)
        restock.clicked.connect(self._restock)
        self.channel.currentIndexChanged.connect(self._reload_lists)
        self.item.currentIndexChanged.connect(self._item_changed)
        form = QFormLayout()
        for label, w in (("Sales channel", self.channel), ("Customer", self.customer), ("Item", self.item),
                         ("Quantity", self.qty), ("Price (variable items)", self.price)):
            form.addRow(label, w)
        left = QVBoxLayout()
        left.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(clear)
        left.addLayout(row)
        left.addWidget(self.cart_table)
        left.addWidget(self.totals)
        pr = QHBoxLayout()
        pr.addWidget(self.pay)
        pr.addWidget(self.ref)
        left.addLayout(pr)
        left.addWidget(checkout)
        right = QVBoxLayout()
        right.addWidget(self.alert)
        right.addWidget(QLabel("Stock levels"))
        right.addWidget(self.stock_table)
        right.addWidget(restock)
        main = QHBoxLayout(self)
        main.addLayout(left, 1)
        main.addLayout(right, 1)
        self.refresh()

    def refresh(self):
        self._reload_lists()
        self._reload_stock()

    def _reload_lists(self):
        def work():
            ch = self.channel.currentData()
            with session_scope() as s:
                items = store.list_items(s, ch)
                members = s.execute(select(Person.id, Person.full_name).join(Member, Member.person_id == Person.id)
                                    .order_by(Person.full_name)).all()
            self.items = {i.id: i for i in items}
            self.item.blockSignals(True)
            self.item.clear()
            for i in items:
                self.item.addItem(f"{i.name}  (Ksh {i.unit_price:,.0f})", i.id)
            self.item.blockSignals(False)
            self.customer.clear()
            if ch == "fan":
                self.customer.addItem("Walk-in fan", None)
            for pid, name in members:
                self.customer.addItem(f"{name} (#{pid})", pid)
            self._item_changed()
            self._clear()
        guarded(self, work)

    def _reload_stock(self):
        def work():
            with session_scope() as s:
                rep = reports.stock_levels(s)
                low = [i.name for i in store.low_stock(s)]
            self.stock_table.load(rep.headers, rep.rows)
            self.alert.setText("RE-ORDER NEEDED: " + ", ".join(low) if low else "")
        guarded(self, work)

    def _item_changed(self):
        it = self.items.get(self.item.currentData())
        variable = bool(it and it.price_min is not None)
        self.price.setEnabled(variable)
        if variable:
            self.price.setRange(float(it.price_min), float(it.price_max))
            self.price.setValue(float(it.unit_price))

    def _add(self):
        iid = self.item.currentData()
        if iid is None:
            return
        it = self.items[iid]
        self.cart.append({"item_id": iid, "qty": self.qty.value(),
                          "unit_price": Decimal(str(self.price.value())) if self.price.isEnabled() else None})
        self._show_cart()

    def _clear(self):
        self.cart = []
        self._show_cart()

    def _show_cart(self):
        rows, priced = [], []
        for ln in self.cart:
            it = self.items[ln["item_id"]]
            p = ln["unit_price"] or it.unit_price
            rows.append([it.name, ln["qty"], p, rules.money(p * ln["qty"])])
            priced.append((ln["qty"], p))
        self.cart_table.load(["Item", "Qty", "Price", "Line total"], rows)
        sub, disc, tot = rules.purchase_totals(priced)
        self.totals.setText(f"Subtotal {sub:,.2f}   Discount {disc:,.2f}   TOTAL Ksh {tot:,.2f}")

    def _checkout(self):
        def work():
            with session_scope() as s:
                res = store.sell(s, self.cart, self.pay.currentText(), self.channel.currentData(),
                                 self.customer.currentData(), self.ref.text().strip() or None, self.user.id)
                self._last = (res.sale.id, res.sale.total, [i.name for i in res.alerts])
        if guarded(self, work):
            sid, total, alerts = self._last
            msg = f"Sale #{sid} complete: Ksh {total:,.2f}."
            if alerts:
                msg += "\n\nRE-ORDER: " + ", ".join(alerts) + " is at or below 20% of max stock."
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Sale complete", msg)
            self.ref.clear()
            self.refresh()

    def _restock(self):
        iid = self.stock_table.selected_id()
        if not need_selection(self, iid, "stock row"):
            return
        qty, ok = QInputDialog.getInt(self, "Restock", "Units received:", 10, 1, 100000)
        if ok:
            def work():
                with session_scope() as s:
                    store.restock(s, iid, qty, self.user.id)
            if guarded(self, work):
                self.refresh()
