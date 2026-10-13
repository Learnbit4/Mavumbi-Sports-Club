"""Mavumbi Sports Club: desktop entry point."""
import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app import db
from app.ui.login import LoginDialog
from app.ui.main_window import MainWindow

STYLE = "QWidget{font-size:13px} QPushButton{padding:6px 12px} QTableWidget{gridline-color:#ddd}"


def main() -> int:
    logging.basicConfig(filename="mavumbi.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    try:
        db.get_engine().connect().close()
    except Exception as e:  # noqa: BLE001
        QMessageBox.critical(None, "Database unavailable",
                             f"Cannot reach the database.\nCheck .env and that MySQL is running.\n\n{e}")
        return 1
    login = LoginDialog()
    if not login.exec():
        return 0
    win = MainWindow(login.user)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
