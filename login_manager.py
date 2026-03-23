from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QApplication,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt5.QtGui import QFont, QPixmap

APP_USERS = {
    # voluntarios/operadores jsjs
    "encargado1": ("balam2026", "encargado"),
    "encargado2": ("balam2026", "encargado"),
    "encargado3": ("balam2026", "encargado"),
    # Admins
    "admin1":     ("balam2026", "admin"),
    "admin2":     ("balam2026", "admin"),
    "admin3":     ("balam2026", "admin"),
    "admin4":     ("balam2026", "admin"),
}

# Minutos de inactividad antes de bloquear
DORMIR = 10

# ── Colores Catppuccin Mocha ──────────────────────────────────
C_BASE    = "#1e1e2e"
C_MANTLE  = "#181825"
C_SURFACE = "#313244"
C_OVERLAY = "#45475a"
C_TEXT    = "#cdd6f4"
C_SUBTEXT = "#6c7086"
C_BLUE    = "#89b4fa"
C_GREEN   = "#a6e3a1"
C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"
C_MAUVE   = "#cba6f7"
C_PEACH   = "#fab387"

class LoginScreen(QWidget):
    """
    Pantalla de login que cubre toda la ventana.
    Emite login_ok(username, nivel) cuando las credenciales son correctas.
    """
    login_ok = pyqtSignal(str, str)   

    def __init__(self, logo_path=None, parent=None):
        super().__init__(parent)
        self.logo_path = logo_path
        self._attempts = 0
        self.setStyleSheet(f"background:{C_BASE};")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)
        root.setSpacing(0)

        card = QFrame()
        card.setFixedWidth(380)
        card.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE};
                border: 1px solid {C_OVERLAY};
                border-radius: 16px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(40, 36, 40, 36)
        lay.setSpacing(16)

        # Logo 
        if self.logo_path:
            import os
            if os.path.exists(self.logo_path):
                lbl_logo = QLabel()
                lbl_logo.setAlignment(Qt.AlignCenter)
                lbl_logo.setStyleSheet("background:transparent; border:none;")
                lbl_logo.setPixmap(
                    QPixmap(self.logo_path).scaledToHeight(54, Qt.SmoothTransformation)
                )
                lay.addWidget(lbl_logo)

        title = QLabel("")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet(f"color:{C_PEACH}; background:transparent; border:none;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel("Iniciar sesión para continuar")
        subtitle.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
        subtitle.setAlignment(Qt.AlignCenter)
        lay.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_OVERLAY}; max-height:1px; border:none;")
        lay.addWidget(sep)

        # Campos
        lbl_u = QLabel("Usuario")
        lbl_u.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
        lay.addWidget(lbl_u)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Ingresa tu usuario")
        self.input_user.setFixedHeight(38)
        self.input_user.setStyleSheet(self._field_style())
        self.input_user.returnPressed.connect(self._do_login)
        lay.addWidget(self.input_user)

        lbl_p = QLabel("Contraseña")
        lbl_p.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
        lay.addWidget(lbl_p)

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("Ingresa tu contraseña")
        self.input_pass.setFixedHeight(38)
        self.input_pass.setStyleSheet(self._field_style())
        self.input_pass.returnPressed.connect(self._do_login)
        lay.addWidget(self.input_pass)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(
            f"color:{C_RED}; font-size:11px; background:transparent; border:none;"
        )
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setWordWrap(True)
        lay.addWidget(self.lbl_error)

        self.btn_login = QPushButton("Entrar")
        self.btn_login.setFixedHeight(42)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background: #2563eb; color: white;
                border: none; border-radius: 8px;
                font-size: 14px; font-weight: 700;
            }}
            QPushButton:hover   {{ background: #1d4ed8; }}
            QPushButton:pressed {{ background: #1e40af; }}
        """)
        self.btn_login.clicked.connect(self._do_login)
        lay.addWidget(self.btn_login)

        root.addWidget(card)

        ver = QLabel("BALAM 2026 · Tesla Lab")
        ver.setStyleSheet(f"color:{C_OVERLAY}; font-size:10px;")
        ver.setAlignment(Qt.AlignCenter)
        root.addSpacing(16)
        root.addWidget(ver)

    def _field_style(self):
        return f"""
            QLineEdit {{
                background: {C_BASE};
                color: {C_TEXT};
                border: 1px solid {C_OVERLAY};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {C_BLUE}; }}
        """

    def _do_login(self):
        user = self.input_user.text().strip()
        pwd  = self.input_pass.text()

        entry = APP_USERS.get(user)
        if entry and entry[0] == pwd:
            nivel = entry[1]
            self.lbl_error.setText("")
            self.input_pass.clear()
            self._attempts = 0
            self.login_ok.emit(user, nivel)
        else:
            self._attempts += 1
            self.lbl_error.setText(
                f"Usuario o contraseña incorrectos.  (intento {self._attempts})"
            )
            self.input_pass.clear()
            self.input_pass.setFocus()

    def reset(self):
        self.input_user.clear()
        self.input_pass.clear()
        self.lbl_error.setText("")
        self._attempts = 0
        self.input_user.setFocus()

class LockOverlay(QWidget):
    """
    Overlay semitransparente que bloquea la ventana principal
    y muestra el login de re-autenticación.
    """
    unlocked = pyqtSignal(str, str)   # (username, nivel)

    def __init__(self, logo_path=None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: rgba(15, 15, 25, 220);")
        self._build_ui(logo_path)

    def _build_ui(self, logo_path):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedWidth(360)
        card.setStyleSheet(f"""
            QFrame {{
                background: {C_SURFACE};
                border: 1px solid {C_OVERLAY};
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(36, 30, 36, 30)
        lay.setSpacing(14)

        icon = QLabel("")
        icon.setFont(QFont("Segoe UI Emoji", 32))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background:transparent; border:none;")
        lay.addWidget(icon)

        title = QLabel("Sesión bloqueada")
        title.setFont(QFont("Segoe UI", 15, QFont.Bold))
        title.setStyleSheet(f"color:{C_YELLOW}; background:transparent; border:none;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)

        sub = QLabel("Inactividad detectada. Vuelve a iniciar sesión.")
        sub.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        lay.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_OVERLAY}; max-height:1px; border:none;")
        lay.addWidget(sep)

        lbl_u = QLabel("Usuario")
        lbl_u.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
        lay.addWidget(lbl_u)

        self.input_user = QLineEdit()
        self.input_user.setPlaceholderText("Usuario")
        self.input_user.setFixedHeight(36)
        self.input_user.setStyleSheet(self._field_style())
        self.input_user.returnPressed.connect(self._do_unlock)
        lay.addWidget(self.input_user)

        lbl_p = QLabel("Contraseña")
        lbl_p.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
        lay.addWidget(lbl_p)

        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.Password)
        self.input_pass.setPlaceholderText("Contraseña")
        self.input_pass.setFixedHeight(36)
        self.input_pass.setStyleSheet(self._field_style())
        self.input_pass.returnPressed.connect(self._do_unlock)
        lay.addWidget(self.input_pass)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(
            f"color:{C_RED}; font-size:11px; background:transparent; border:none;"
        )
        self.lbl_error.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_error)

        btn = QPushButton("Desbloquear")
        btn.setFixedHeight(40)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: #2563eb; color: white;
                border: none; border-radius: 7px;
                font-size: 13px; font-weight: 700;
            }}
            QPushButton:hover   {{ background: #1d4ed8; }}
            QPushButton:pressed {{ background: #1e40af; }}
        """)
        btn.clicked.connect(self._do_unlock)
        lay.addWidget(btn)

        root.addWidget(card)

    def _field_style(self):
        return f"""
            QLineEdit {{
                background: {C_BASE};
                color: {C_TEXT};
                border: 1px solid {C_OVERLAY};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {C_BLUE}; }}
        """

    def _do_unlock(self):
        user = self.input_user.text().strip()
        pwd  = self.input_pass.text()

        entry = APP_USERS.get(user)
        if entry and entry[0] == pwd:
            self.lbl_error.setText("")
            self.input_pass.clear()
            self.unlocked.emit(user, entry[1])
        else:
            self.lbl_error.setText("Credenciales incorrectas.")
            self.input_pass.clear()
            self.input_pass.setFocus()

    def show_and_focus(self):
        self.input_user.clear()
        self.input_pass.clear()
        self.lbl_error.setText("")
        self.show()
        self.raise_()
        self.input_user.setFocus()

class SessionManager:
    """
    Controla el estado de sesión y el auto-bloqueo por inactividad.

    Uso en ESP32Tester:
        self._session = SessionManager(main_window, logo_path)
        self._session.session_changed.connect(self._on_session_changed)
    """

    class _Signals(QWidget):
        session_changed = pyqtSignal(str, str)   

    def __init__(self, main_window, logo_path=None):
        self._win        = main_window
        self._username   = ""
        self._nivel      = ""
        self._sig        = self._Signals()
        self.session_changed = self._sig.session_changed

        QApplication.instance().installEventFilter(self._sig)
        self._sig.eventFilter = self._event_filter

        self._timer = QTimer()
        self._timer.setInterval(DORMIR * 60 * 1000)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._lock)

        self._overlay = None
        self._logo    = logo_path

    @property
    def username(self): return self._username

    @property
    def nivel(self): return self._nivel

    @property
    def logged_in(self): return bool(self._username)

    def on_login(self, username: str, nivel: str):
        self._username = username
        self._nivel    = nivel
        self._timer.start()
        if self._overlay:
            self._overlay.hide()
        self.session_changed.emit(username, nivel)

    def on_logout(self):
        self._username = ""
        self._nivel    = ""
        self._timer.stop()
        self.session_changed.emit("", "")

    def _lock(self):
        if not self._username:
            return
        if self._overlay is None:
            self._overlay = LockOverlay(self._logo, self._win)
            self._overlay.unlocked.connect(self.on_login)
        self._overlay.resize(self._win.size())
        self._overlay.move(0, 0)
        self._overlay.show_and_focus()

    def _reset_timer(self):
        if self._username:
            self._timer.start()

    def _event_filter(self, obj, event):
        if event.type() in (
            QEvent.MouseMove, QEvent.MouseButtonPress,
            QEvent.KeyPress, QEvent.Wheel,
        ):
            self._reset_timer()
        return False 

    def resize_overlay(self, size):
        if self._overlay and self._overlay.isVisible():
            self._overlay.resize(size)
