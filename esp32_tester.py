import sys
import os
import re
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStatusBar, QTabWidget, QStackedWidget, QLabel, QPushButton,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

from login_manager import LoginScreen, SessionManager
from validacion    import TabValidacion
from tab_buscador  import TabBuscador
from tab_dashboard import TabDashboard
from tab_admin     import TabAdmin
from tab_flasher   import TabFlasher
from tab_tester    import TabTester


# ══════════════════════════════════════════════════════════════
#  CONFIGURACION
# ══════════════════════════════════════════════════════════════

SHEET_ID      = '13WIYurPQvRztU1xpUru8-COzgfdPzqvTP4hEZM6pX2I'
HEADER_ROW    = 1
COL_ESTADO    = 'A'
COL_ID        = 'B'
COL_QR        = 'C'
COL_TIMESTAMP = 'D'
COL_NOTAS     = 'E'

SHEET_MAP = {
    "ESP32":       "ESP32",
    "ROBOFUT":     "Robofut",
    "TODOTERRENO": "Todoterreno",
    "STEM_SR":     "STEM SR",
    "STEM_JR":     "STEM JR",
    "DRONES":      "Drones",
    "IOT":         "IOT",
}

QR_PATTERN = re.compile(
    r'^(ESP32|ROBOFUT|TODOTERRENO|STEM_SR|STEM_JR|DRONES|IOT)-BALAM-(\d+)$',
    re.IGNORECASE
)

# Pestanas bloqueadas sin login
LOCKED_TABS = {0, 1, 2}   # Tester, Validacion QR, Buscador


# ══════════════════════════════════════════════════════════════
#  STYLESHEET — Catppuccin Mocha
# ══════════════════════════════════════════════════════════════

STYLE = """
QMainWindow, QWidget {
    background: #1e1e2e; color: #cdd6f4;
    font-family: 'Segoe UI', sans-serif; font-size: 12px;
}
QTabWidget::pane {
    border: 1px solid #45475a; border-radius: 6px; background: #1e1e2e;
}
QTabBar::tab {
    background: #313244; color: #cdd6f4; padding: 8px 22px;
    border-bottom: 2px solid transparent;
    font-size: 12px; font-weight: 600; min-width: 140px;
}
QTabBar::tab:selected  { background: #1e1e2e; color: #89b4fa; border-bottom: 2px solid #89b4fa; }
QTabBar::tab:hover     { background: #45475a; }
QTabBar::tab:disabled  { color: #45475a; background: #181825; }
QGroupBox {
    border: 1px solid #45475a; border-radius: 6px; margin-top: 10px;
    font-weight: bold; color: #89b4fa; padding: 6px;
}
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
QPushButton {
    background: #313244; color: #cdd6f4; border: 1px solid #45475a;
    border-radius: 5px; padding: 5px 12px; font-size: 12px;
}
QPushButton:hover    { background: #45475a; }
QPushButton:pressed  { background: #585b70; }
QPushButton:checked  { background: #a6e3a1; color: #1e1e2e; }
QPushButton:disabled { background: #252535; color: #585b70; border-color: #313244; }
QPushButton[primary="true"]          { background: #2563eb; color: white; border: none; font-weight: 700; }
QPushButton[primary="true"]:hover    { background: #1d4ed8; }
QPushButton[primary="true"]:disabled { background: #1e3a6e; color: #7a9fd6; }
QPushButton[success="true"]          { background: #14532d; color: #86efac; border: 1px solid #22c55e; font-weight: 700; }
QPushButton[success="true"]:hover    { background: #166534; }
QPushButton[danger="true"]           { background: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; font-weight: 700; }
QPushButton[danger="true"]:hover     { background: #991b1b; }
QComboBox, QLineEdit, QSpinBox {
    background: #313244; color: #cdd6f4; border: 1px solid #45475a;
    border-radius: 4px; padding: 4px 8px;
}
QComboBox:focus, QLineEdit:focus  { border-color: #89b4fa; }
QComboBox::drop-down              { border: none; }
QComboBox QAbstractItemView       { background: #313244; color: #cdd6f4; border: 1px solid #45475a; }
QTextEdit {
    background: #11111b; color: #a6e3a1;
    border: 1px solid #45475a; border-radius: 4px;
}
QProgressBar {
    background: #45475a; border-radius: 4px; border: none;
    color: #cdd6f4; font-size: 11px;
}
QProgressBar::chunk { background: #89b4fa; border-radius: 4px; }
QSlider::groove:horizontal {
    height: 6px; background: #45475a; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #89b4fa; width: 16px; height: 16px;
    margin: -5px 0; border-radius: 8px;
}
QSlider::sub-page:horizontal { background: #89b4fa; border-radius: 3px; }
QStatusBar        { background: #181825; color: #6c7086; }
QSplitter::handle { background: #45475a; width: 2px; }
QLabel            { color: #cdd6f4; }
QScrollBar:vertical {
    background: #181825; width: 8px; border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #45475a; border-radius: 4px; min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


# ══════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL
# ══════════════════════════════════════════════════════════════

class ESP32Tester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tesla Lab — ESP32 Tester  BALAM 2026")
        self.setMinimumSize(1100, 740)
        self.logo_path = self._find_logo()

        # SessionManager ANTES de _build_ui para que las lambdas del Flasher funcionen
        self._session = SessionManager(self, self.logo_path)
        self._session.session_changed.connect(self._on_session_changed)

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._show_login()

    def _find_logo(self) -> str:
        base = os.path.dirname(os.path.abspath(__file__))
        for candidate in [
            os.path.join(base, "imgs", "LOGO TESLA-13.png"),
            os.path.join(base, "LOGO_TESLA-13.png"),
        ]:
            if os.path.exists(candidate):
                return candidate
        return None

    # ── Construccion de UI ────────────────────────────────────────
    def _build_ui(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo.")

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Stack: indice 0 = login, indice 1 = app
        self._main_stack = QStackedWidget()

        # Pantalla de login
        self._login_screen = LoginScreen(logo_path=self.logo_path)
        self._login_screen.login_ok.connect(self._on_login)
        self._main_stack.addWidget(self._login_screen)   # 0

        # App principal
        app_widget = QWidget()
        app_layout = QVBoxLayout(app_widget)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(0)
        app_layout.addWidget(self._build_banner())
        app_layout.addWidget(self._build_tabs(), 1)
        self._main_stack.addWidget(app_widget)            # 1

        root.addWidget(self._main_stack)

    def _build_banner(self) -> QWidget:
        banner = QWidget()
        banner.setStyleSheet("background:#181825; border-bottom:1px solid #45475a;")
        banner.setFixedHeight(52)
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(14, 6, 14, 6)

        if self.logo_path:
            lbl_logo = QLabel()
            lbl_logo.setPixmap(
                QPixmap(self.logo_path).scaledToHeight(36, Qt.SmoothTransformation)
            )
        else:
            lbl_logo = QLabel("TESLA LAB")
            lbl_logo.setFont(QFont("Segoe UI", 16, QFont.Bold))
            lbl_logo.setStyleSheet("color:#fab387;")
        lay.addWidget(lbl_logo)
        lay.addStretch()

        # Badge de usuario activo
        self._lbl_user_badge = QLabel("")
        self._lbl_user_badge.setStyleSheet(
            "color:#a6e3a1; font-size:11px; font-weight:600; "
            "padding:2px 10px; background:#14532d; border-radius:4px;"
        )
        self._lbl_user_badge.hide()
        lay.addWidget(self._lbl_user_badge)

        # Boton cerrar sesion
        self._btn_logout = QPushButton("Cerrar sesion")
        self._btn_logout.setFixedHeight(28)
        self._btn_logout.setStyleSheet(
            "QPushButton { background:#313244; color:#f38ba8; "
            "border:1px solid #f38ba8; border-radius:4px; "
            "font-size:11px; padding:2px 10px; }"
            "QPushButton:hover { background:#3b1a1a; }"
        )
        self._btn_logout.clicked.connect(self._on_logout)
        self._btn_logout.hide()
        lay.addWidget(self._btn_logout)

        sub = QLabel("Tesla Lab — Test Station")
        sub.setStyleSheet("color:#585b70; font-size:11px; margin-left:12px;")
        lay.addWidget(sub)
        return banner

    def _build_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Tester con GUI animada (reemplaza el viejo Tester Serial)
        self.tab_tester = TabTester()

        self.tab_validacion = TabValidacion(
            logo_path=self.logo_path,
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            qr_pattern=QR_PATTERN,
            col_config=(COL_ESTADO, COL_ID, COL_QR, COL_TIMESTAMP, COL_NOTAS),
            header_row=HEADER_ROW,
        )
        self.tab_buscador = TabBuscador(
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            header_row=HEADER_ROW,
        )
        self.tab_dashboard = TabDashboard(
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            header_row=HEADER_ROW,
        )
        self.tab_admin = TabAdmin(
            sheet_id=SHEET_ID,
            sheet_map=SHEET_MAP,
            header_row=HEADER_ROW,
        )
        # Admin elige los .bin, encargado flashea
        self.tab_flasher = TabFlasher(
            is_admin_fn=lambda: self._session.nivel == "admin"
        )

        self.tabs.addTab(self.tab_tester,     "Tester")          # 0
        self.tabs.addTab(self.tab_validacion, "Validacion QR")   # 1
        self.tabs.addTab(self.tab_buscador,   "Buscador")        # 2
        self.tabs.addTab(self.tab_dashboard,  "Dashboard")       # 3
        self.tabs.addTab(self.tab_admin,      "Admin")           # 4
        self.tabs.addTab(self.tab_flasher,    "Flasher")         # 5

        # Conectar status bar
        self.tab_tester.status_msg.connect(self.status_bar.showMessage)
        self.tab_validacion.status_msg.connect(self.status_bar.showMessage)
        self.tab_buscador.status_msg.connect(self.status_bar.showMessage)
        self.tab_dashboard.status_msg.connect(self.status_bar.showMessage)
        self.tab_admin.status_msg.connect(self.status_bar.showMessage)
        self.tab_flasher.status_msg.connect(self.status_bar.showMessage)

        self.tabs.currentChanged.connect(self._on_tab_changed)
        return self.tabs

    # ── Login / Sesion ────────────────────────────────────────────
    def _show_login(self):
        self._login_screen.reset()
        self._main_stack.setCurrentIndex(0)
        self._set_tabs_locked(True)
        self.status_bar.showMessage("Inicia sesion para continuar.")

    def _on_login(self, username: str, nivel: str):
        self._session.on_login(username, nivel)

    def _on_logout(self):
        self._session.on_logout()
        self._show_login()

    def _on_session_changed(self, username: str, nivel: str):
        if username:
            # Propagar usuario a las pestanas que lo necesitan
            self.tab_validacion.set_encargado(username)
            self.tab_flasher.notify_login()

            self._main_stack.setCurrentIndex(1)
            self._set_tabs_locked(False)

            nivel_label = "Admin" if nivel == "admin" else "Encargado"
            self._lbl_user_badge.setText(f"  {username}  [{nivel_label}]")
            self._lbl_user_badge.show()
            self._btn_logout.show()
            self.status_bar.showMessage(
                f"Sesion iniciada: {username} ({nivel_label}) — "
                f"Auto-bloqueo en 10 min de inactividad."
            )
        else:
            self._lbl_user_badge.hide()
            self._btn_logout.hide()

    def _set_tabs_locked(self, locked: bool):
        for idx in LOCKED_TABS:
            self.tabs.setTabEnabled(idx, not locked)
        if locked:
            self.tabs.setCurrentIndex(3)   # Dashboard siempre visible

    def _on_tab_changed(self, idx: int):
        if not self._session.logged_in and idx in LOCKED_TABS:
            self.tabs.setCurrentIndex(3)

    # ── Eventos de ventana ────────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._session.resize_overlay(self.centralWidget().size())

    def closeEvent(self, event):
        self.tab_tester.cleanup()
        self.tab_validacion.cleanup()
        self.tab_buscador.cleanup()
        self.tab_dashboard.cleanup()
        self.tab_admin.cleanup()
        self.tab_flasher.cleanup()
        event.accept()


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = ESP32Tester()
    window.show()
    sys.exit(app.exec_())
