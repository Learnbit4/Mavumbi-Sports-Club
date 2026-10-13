from __future__ import annotations

import logging
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QMessageBox, QTableWidget, QTableWidgetItem

from ..errors import ClubError

log = logging.getLogger("mavumbi")


def fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return f"{v:,.2f}"
    return str(v)


class DataTable(QTableWidget):
    """Read-only table. Column 0 should hold the record id."""

    def __init__(self):
        super().__init__()
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)

    def load(self, headers: list[str], rows: list[list]) -> None:
        self.clear()
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                it = QTableWidgetItem(fmt(v))
                if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.setItem(r, c, it)
        self.resizeColumnsToContents()

    def selected_id(self, col: int = 0) -> int | None:
        row = self.currentRow()
        if row < 0 or self.item(row, col) is None:
            return None
        try:
            return int(self.item(row, col).text())
        except ValueError:
            return None


def guarded(parent, fn, ok_msg: str | None = None) -> bool:
    """Run fn(); show business-rule errors as warnings, unexpected ones as a critical box. True on success."""
    try:
        fn()
    except ClubError as e:
        QMessageBox.warning(parent, "Cannot complete", str(e))
        return False
    except Exception as e:  # noqa: BLE001 - last line of defence for the UI
        log.exception("Unexpected error")
        QMessageBox.critical(parent, "Unexpected error", f"{type(e).__name__}: {e}\n\nNothing was saved.")
        return False
    if ok_msg:
        QMessageBox.information(parent, "Done", ok_msg)
    return True


def need_selection(parent, value, what: str) -> bool:
    if value is None:
        QMessageBox.information(parent, "Select a row", f"Select a {what} first.")
        return False
    return True
