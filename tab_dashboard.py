import socket
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QSpinBox,
    QProgressBar, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPainterPath


# ══════════════════════════════════════════════════════════════
#  COLORES Catppuccin Mocha
# ══════════════════════════════════════════════════════════════
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
C_TEAL    = "#94e2d5"
C_PEACH   = "#fab387"
C_SKY     = "#89dceb"

CAT_COLORS = {
    "ESP32":       C_BLUE,
    "Robofut":     C_MAUVE,
    "Todoterreno": C_TEAL,
    "STEM SR":     C_PEACH,
    "STEM JR":     C_YELLOW,
    "Drones":      C_SKY,
    "IOT":         C_GREEN,
}

CAT_ICONS = {
    "ESP32":       "",
    "Robofut":     "",
    "Todoterreno": "",
    "STEM SR":     "",
    "STEM JR":     "",
    "Drones":      "",
    "IOT":         "",
}


# ══════════════════════════════════════════════════════════════
#  HILO LECTOR (dashboard)
# ══════════════════════════════════════════════════════════════
class DashboardReader(QThread):
    """Lee todas las hojas y emite resumen por categoría."""
    data_ready = pyqtSignal(dict)   # {sheet_name: {total, ok, fail, last_ts}}
    error      = pyqtSignal(str)

    def __init__(self, sheet_id, sheet_map, header_row=1):
        super().__init__()
        self.sheet_id   = sheet_id
        self.sheet_map  = sheet_map
        self.header_row = header_row

    def run(self):
        try:
            import gspread
            gc = gspread.oauth(
                credentials_filename='credentials.json',
                authorized_user_filename='token.json'
            )
            book = gc.open_by_key(self.sheet_id)
            summary = {}

            for key, sheet_name in self.sheet_map.items():
                try:
                    ws = book.worksheet(sheet_name)
                    vals = ws.get_all_values()[self.header_row:]
                    total = 0
                    ok = 0
                    fail = 0
                    last_ts = ""
                    for row in vals:
                        if len(row) < 3:
                            continue
                        estado = (row[0] if row else "").strip()
                        qr     = (row[2] if len(row) > 2 else "").strip()
                        ts     = (row[3] if len(row) > 3 else "").strip()
                        if not qr:
                            continue
                        total += 1
                        if estado.upper() == "OK":
                            ok += 1
                        elif estado.upper() == "FAIL":
                            fail += 1
                        if ts:
                            last_ts = ts
                    summary[sheet_name] = {
                        "total": total,
                        "ok":    ok,
                        "fail":  fail,
                        "last":  last_ts,
                    }
                except Exception:
                    summary[sheet_name] = {"total": 0, "ok": 0, "fail": 0, "last": "—"}

            self.data_ready.emit(summary)

        except FileNotFoundError:
            self.error.emit("credentials.json / token.json no encontrado")
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  TARJETA DE CATEGORÍA
# ══════════════════════════════════════════════════════════════
CARD_STYLE = """
QFrame#DashCard {{
    background: {bg};
    border: 1px solid {border};
    border-left: 4px solid {accent};
    border-radius: 10px;
}}
"""

class CategoryCard(QFrame):
    """Tarjeta visual para una categoría."""

    def __init__(self, name: str, accent: str, icon: str):
        super().__init__()
        self.setObjectName("DashCard")
        self.accent = accent
        self.setStyleSheet(CARD_STYLE.format(
            bg="#242434", border=C_OVERLAY, accent=accent
        ))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(148)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Encabezado: icono + nombre
        hdr = QHBoxLayout()
        lbl_icon = QLabel(icon)
        lbl_icon.setFont(QFont("Segoe UI Emoji", 20))
        lbl_icon.setStyleSheet("background:transparent;")
        lbl_name = QLabel(name)
        lbl_name.setFont(QFont("Segoe UI", 13, QFont.Bold))
        lbl_name.setStyleSheet(f"color:{accent}; background:transparent;")
        hdr.addWidget(lbl_icon)
        hdr.addWidget(lbl_name, 1)
        layout.addLayout(hdr)

        # Contadores
        counts = QHBoxLayout()
        self.lbl_total = self._counter("Total", "0", C_TEXT)
        self.lbl_ok    = self._counter("OK",    "0", C_GREEN)
        self.lbl_fail  = self._counter("FAIL",  "0", C_RED)
        for w in [self.lbl_total, self.lbl_ok, self.lbl_fail]:
            counts.addWidget(w, 1)
        layout.addLayout(counts)

        # Barra de progreso OK %
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_OVERLAY};
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.bar)

        # Último registro
        self.lbl_last = QLabel("Último: —")
        self.lbl_last.setStyleSheet(f"color:{C_SUBTEXT}; font-size:10px; background:transparent;")
        layout.addWidget(self.lbl_last)

    def _counter(self, label, value, color):
        w = QLabel()
        w.setAlignment(Qt.AlignCenter)
        w.setStyleSheet("background:transparent;")
        w.setText(
            f'<div style="text-align:center;">'
            f'<span style="color:{C_SUBTEXT}; font-size:10px;">{label}</span><br>'
            f'<span style="color:{color}; font-size:22px; font-weight:700;">{value}</span>'
            f'</div>'
        )
        w.setTextFormat(Qt.RichText)
        return w

    def _set_counter(self, lbl, label, value, color):
        lbl.setText(
            f'<div style="text-align:center;">'
            f'<span style="color:{C_SUBTEXT}; font-size:10px;">{label}</span><br>'
            f'<span style="color:{color}; font-size:22px; font-weight:700;">{value}</span>'
            f'</div>'
        )

    def update_data(self, total: int, ok: int, fail: int, last_ts: str):
        self._set_counter(self.lbl_total, "Total", str(total), C_TEXT)
        self._set_counter(self.lbl_ok,    "OK",    str(ok),    C_GREEN)
        self._set_counter(self.lbl_fail,  "FAIL",  str(fail),  C_RED)
        pct = int((ok / total) * 100) if total > 0 else 0
        self.bar.setValue(pct)
        self.lbl_last.setText(f"Último: {last_ts or '—'}")

    def set_error(self):
        self._set_counter(self.lbl_total, "Total", "?", C_OVERLAY)
        self._set_counter(self.lbl_ok,    "OK",    "?", C_OVERLAY)
        self._set_counter(self.lbl_fail,  "FAIL",  "?", C_OVERLAY)
        self.bar.setValue(0)
        self.lbl_last.setText("Error al leer")


# ══════════════════════════════════════════════════════════════
#  BARRA DE ESTADO DEL SISTEMA
# ══════════════════════════════════════════════════════════════
def _get_network_name() -> str:
    """Intenta obtener el nombre de red (hostname como fallback)."""
    try:
        import subprocess
        # Windows
        result = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            stderr=subprocess.DEVNULL, timeout=3
        ).decode("latin-1", errors="replace")
        for line in result.splitlines():
            if "SSID" in line and "BSSID" not in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    ssid = parts[1].strip()
                    if ssid:
                        return ssid
    except Exception:
        pass
    try:
        import subprocess
        # Linux / macOS
        result = subprocess.check_output(
            ["iwgetid", "-r"],
            stderr=subprocess.DEVNULL, timeout=3
        ).decode().strip()
        if result:
            return result
    except Exception:
        pass
    # Fallback: nombre del host
    try:
        return socket.gethostname()
    except Exception:
        return "Red desconocida"


# ══════════════════════════════════════════════════════════════
#  PESTAÑA DASHBOARD
# ══════════════════════════════════════════════════════════════
class TabDashboard(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, sheet_id, sheet_map, header_row=1):
        super().__init__()
        self.sheet_id   = sheet_id
        self.sheet_map  = sheet_map
        self.header_row = header_row
        self._worker    = None
        self._cards     = {}   # {sheet_name: CategoryCard}

        self._build_ui()

        # Timer de reloj (1 seg)
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)

        # Timer de red (cada 30 seg)
        self._net_timer = QTimer(self)
        self._net_timer.timeout.connect(self._refresh_network)
        self._net_timer.start(30_000)
        self._refresh_network()

        # Timer de auto-refresh
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        root.addWidget(self._build_sysbar())
        root.addWidget(self._build_control_bar())
        root.addWidget(self._build_cards_area(), 1)

    def _build_sysbar(self):
        """Barra de estado: hora + red."""
        bar = QWidget()
        bar.setStyleSheet(f"""
            background: {C_MANTLE};
            border-radius: 8px;
        """)
        bar.setFixedHeight(42)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)

        dot = QLabel("Hora: ")
        dot.setStyleSheet(f"color:{C_GREEN}; font-size:14px;")
        lay.addWidget(dot)

        self.lbl_hora = QLabel("00:00:00")
        self.lbl_hora.setFont(QFont("Consolas", 14, QFont.Bold))
        self.lbl_hora.setStyleSheet(f"color:{C_BLUE};")
        lay.addWidget(self.lbl_hora)

        sep = QLabel("  |  ")
        sep.setStyleSheet(f"color:{C_OVERLAY};")
        lay.addWidget(sep)

        lbl_red_prefix = QLabel("Red:")
        lbl_red_prefix.setStyleSheet(f"color:{C_SUBTEXT}; font-size:12px;")
        lay.addWidget(lbl_red_prefix)

        self.lbl_red = QLabel("Detectando red…")
        self.lbl_red.setStyleSheet(f"color:{C_TEAL}; font-size:12px; font-weight:600;")
        lay.addWidget(self.lbl_red)

        lay.addStretch()

        self.lbl_refresh_status = QLabel("Sin datos")
        self.lbl_refresh_status.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        lay.addWidget(self.lbl_refresh_status)

        return bar

    def _build_control_bar(self):
        box = QGroupBox("Control de auto-actualización")
        box.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {C_OVERLAY};
                border-radius: 8px;
                margin-top: 10px;
                font-weight: bold;
                color: {C_BLUE};
                padding: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }}
        """)
        lay = QHBoxLayout(box)
        lay.setSpacing(14)

        lay.addWidget(self._lbl("Intervalo:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(5, 300)
        self.spin_interval.setValue(30)
        self.spin_interval.setSuffix(" seg")
        self.spin_interval.setFixedWidth(100)
        self.spin_interval.setStyleSheet(f"""
            QSpinBox {{
                background: {C_SURFACE};
                color: {C_TEXT};
                border: 1px solid {C_OVERLAY};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
        """)
        lay.addWidget(self.spin_interval)

        self.btn_auto = QPushButton("Iniciar auto-refresh")
        self.btn_auto.setCheckable(True)
        self.btn_auto.setFixedWidth(180)
        self.btn_auto.setFixedHeight(32)
        self.btn_auto.setStyleSheet(f"""
            QPushButton {{
                background: {C_SURFACE};
                color: {C_TEXT};
                border: 1px solid {C_OVERLAY};
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:checked {{
                background: #14532d;
                color: {C_GREEN};
                border: 1px solid #22c55e;
            }}
        """)
        self.btn_auto.clicked.connect(self._toggle_auto)
        lay.addWidget(self.btn_auto)

        self.btn_now = QPushButton("Actualizar ahora")
        self.btn_now.setProperty("primary", True)
        self.btn_now.setFixedWidth(170)
        self.btn_now.setFixedHeight(32)
        self.btn_now.clicked.connect(self._refresh_now)
        lay.addWidget(self.btn_now)

        lay.addStretch()

        # Countdown
        self.lbl_countdown = QLabel("")
        self.lbl_countdown.setStyleSheet(f"color:{C_YELLOW}; font-size:12px; font-weight:600;")
        lay.addWidget(self.lbl_countdown)

        self._countdown_val = 0
        self._countdown_timer = QTimer(self)
        self._countdown_timer.timeout.connect(self._tick_countdown)

        return box

    def _build_cards_area(self):
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(14)

        categories = list(self.sheet_map.values())
        for i, name in enumerate(categories):
            accent = CAT_COLORS.get(name, C_BLUE)
            icon   = CAT_ICONS.get(name, "")
            card   = CategoryCard(name, accent, icon)
            self._cards[name] = card
            row, col = divmod(i, 4)
            grid.addWidget(card, row, col)

        # Llenar espacios vacíos en la última fila
        total = len(categories)
        remainder = total % 4
        if remainder:
            for col in range(remainder, 4):
                placeholder = QWidget()
                placeholder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                row = total // 4
                grid.addWidget(placeholder, row, col)

        grid.setRowStretch(grid.rowCount(), 1)
        return container

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{C_TEXT}; font-weight:600;")
        return l

    # ── Acciones ────────────────────────────────────────────────
    def _tick_clock(self):
        self.lbl_hora.setText(datetime.now().strftime("%H:%M:%S"))

    def _refresh_network(self):
        net = _get_network_name()
        self.lbl_red.setText(net)

    def _toggle_auto(self, checked: bool):
        if checked:
            interval_ms = self.spin_interval.value() * 1000
            self._refresh_timer.start(interval_ms)
            self._countdown_val = self.spin_interval.value()
            self._countdown_timer.start(1000)
            self.btn_auto.setText("Pausar auto-refresh")
            self.status_msg.emit(f"Auto-refresh cada {self.spin_interval.value()} seg.")
            self._refresh_now()
        else:
            self._refresh_timer.stop()
            self._countdown_timer.stop()
            self.btn_auto.setText("Iniciar auto-refresh")
            self.lbl_countdown.setText("")
            self.status_msg.emit("Auto-refresh pausado.")

    def _tick_countdown(self):
        self._countdown_val -= 1
        if self._countdown_val <= 0:
            self._countdown_val = self.spin_interval.value()
        self.lbl_countdown.setText(f"Próximo refresh en {self._countdown_val}s")

    def _auto_refresh(self):
        self._countdown_val = self.spin_interval.value()
        self._refresh_now()

    def _refresh_now(self):
        if self._worker and self._worker.isRunning():
            return  # ya hay una lectura en curso
        self.btn_now.setEnabled(False)
        self.lbl_refresh_status.setText("Leyendo Sheets…")
        self.status_msg.emit("Dashboard: consultando Google Sheets…")

        self._worker = DashboardReader(
            sheet_id=self.sheet_id,
            sheet_map=self.sheet_map,
            header_row=self.header_row,
        )
        self._worker.data_ready.connect(self._on_data)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_data(self, summary: dict):
        for sheet_name, stats in summary.items():
            card = self._cards.get(sheet_name)
            if card:
                card.update_data(
                    total=stats["total"],
                    ok=stats["ok"],
                    fail=stats["fail"],
                    last_ts=stats["last"],
                )
        ts = datetime.now().strftime("%H:%M:%S")
        self.lbl_refresh_status.setText(f"Actualizado: {ts}")
        self.btn_now.setEnabled(True)
        self.status_msg.emit(f"Dashboard actualizado a las {ts}.")

    def _on_error(self, msg: str):
        for card in self._cards.values():
            card.set_error()
        self.lbl_refresh_status.setText(f"Error: {msg}")
        self.btn_now.setEnabled(True)
        self.status_msg.emit(f"Dashboard error: {msg}")

    def cleanup(self):
        self._clock_timer.stop()
        self._net_timer.stop()
        self._refresh_timer.stop()
        self._countdown_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
