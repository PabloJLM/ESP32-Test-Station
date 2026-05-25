import os, re, subprocess, serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QTextEdit, QProgressBar, QFileDialog, QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

BAUD_RATE    = 115200
FLASH_OFFSET = "0x0"

# ── Bins builtin — rutas relativas al .py ────────────────────
_BASE = os.path.dirname(os.path.abspath(__file__))

_BUILTIN_MAESTRO = os.path.join(
    _BASE, "maestro", "build",
    "esp32.esp32.esp32",
    "maestro.ino.bin"
)
_BUILTIN_SLAVE = os.path.join(
    _BASE, "slave_main", "build",
    "esp32.esp32.esp32wrover",
    "slave_main.ino.bin"
)

# Overrides en runtime (solo admin)
_bin_maestro_override = ""
_bin_slave_override   = ""

def _get_bin_maestro() -> str:
    return _bin_maestro_override if _bin_maestro_override else _BUILTIN_MAESTRO

def _get_bin_slave() -> str:
    return _bin_slave_override if _bin_slave_override else _BUILTIN_SLAVE

def _set_bin_maestro(path: str):
    global _bin_maestro_override
    _bin_maestro_override = path

def _set_bin_slave(path: str):
    global _bin_slave_override
    _bin_slave_override = path

def _reset_overrides():
    global _bin_maestro_override, _bin_slave_override
    _bin_maestro_override = ""
    _bin_slave_override   = ""


C_BASE    = "#1e1e2e"; C_MANTLE  = "#181825"; C_SURFACE = "#313244"
C_OVERLAY = "#45475a"; C_TEXT    = "#cdd6f4"; C_SUBTEXT = "#6c7086"
C_BLUE    = "#89b4fa"; C_GREEN   = "#a6e3a1"; C_RED     = "#f38ba8"
C_YELLOW  = "#f9e2af"; C_MAUVE   = "#cba6f7"; C_TEAL    = "#94e2d5"


class FlashWorker(QThread):
    output   = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, port: str, bin_path: str, baud: int = BAUD_RATE):
        super().__init__()
        self.port = port; self.bin_path = bin_path; self.baud = baud

    def run(self):
        import sys
        cmd = [sys.executable, "-m", "esptool",
               "--chip", "esp32", "--port", self.port,
               "--baud", str(self.baud), "write_flash", FLASH_OFFSET, self.bin_path]
        self.output.emit(f"Ejecutando: {' '.join(cmd)}\n")
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip(); self.output.emit(line)
                m = re.search(r'\((\d+)\s*%\)', line)
                if m: self.progress.emit(int(m.group(1)))
            proc.wait()
            if proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Flash completado exitosamente.")
            else:
                self.finished.emit(False, f"esptool termino con codigo {proc.returncode}.")
        except FileNotFoundError:
            self.finished.emit(False,
                "esptool no encontrado.\nInstalar: pip install esptool")
        except Exception as e:
            self.finished.emit(False, str(e))


class TabFlasher(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, is_admin_fn=None):
        super().__init__()
        self._is_admin = is_admin_fn or (lambda: False)
        self._worker   = None
        self._build_ui()
        self._refresh_ports()

    def notify_login(self):
        self._refresh_bin_labels()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)
        root.addWidget(self._build_bin_section())
        root.addWidget(self._build_flash_section())
        root.addWidget(self._build_output_section(), 1)

    def _build_bin_section(self):
        box = QGroupBox("Archivos de firmware (.bin)")
        box.setStyleSheet(self._gs(C_BLUE))
        grid = QGridLayout(box); grid.setSpacing(10)

        # ── Maestro ──────────────────────────────────────────
        grid.addWidget(self._lbl("Maestro:"), 0, 0)
        self._lbl_maestro = QLabel()
        self._lbl_maestro.setWordWrap(True)
        grid.addWidget(self._lbl_maestro, 0, 1)

        row_m = QHBoxLayout()
        self._btn_bin_maestro = QPushButton("Override .bin")
        self._btn_bin_maestro.setFixedWidth(120)
        self._btn_bin_maestro.setStyleSheet(self._bs())
        self._btn_bin_maestro.clicked.connect(lambda: self._elegir_bin("maestro"))
        self._btn_reset_maestro = QPushButton("Restaurar")
        self._btn_reset_maestro.setFixedWidth(90)
        self._btn_reset_maestro.setStyleSheet(self._bs())
        self._btn_reset_maestro.clicked.connect(lambda: self._restore_bin("maestro"))
        row_m.addWidget(self._btn_bin_maestro)
        row_m.addWidget(self._btn_reset_maestro)
        grid.addLayout(row_m, 0, 2)

        # ── Slave Principal ───────────────────────────────────
        grid.addWidget(self._lbl("Slave Principal:"), 1, 0)
        self._lbl_slave = QLabel()
        self._lbl_slave.setWordWrap(True)
        grid.addWidget(self._lbl_slave, 1, 1)

        row_s = QHBoxLayout()
        self._btn_bin_slave = QPushButton("Override .bin")
        self._btn_bin_slave.setFixedWidth(120)
        self._btn_bin_slave.setStyleSheet(self._bs())
        self._btn_bin_slave.clicked.connect(lambda: self._elegir_bin("slave"))
        self._btn_reset_slave = QPushButton("Restaurar")
        self._btn_reset_slave.setFixedWidth(90)
        self._btn_reset_slave.setStyleSheet(self._bs())
        self._btn_reset_slave.clicked.connect(lambda: self._restore_bin("slave"))
        row_s.addWidget(self._btn_bin_slave)
        row_s.addWidget(self._btn_reset_slave)
        grid.addLayout(row_s, 1, 2)

        grid.setColumnStretch(1, 1)
        self._refresh_bin_labels()
        return box

    def _build_flash_section(self):
        box = QGroupBox("Flashear")
        box.setStyleSheet(self._gs(C_TEAL))
        lay = QHBoxLayout(box); lay.setSpacing(14)
        lay.addWidget(self._lbl("Puerto:"))
        self._combo_port = QComboBox(); self._combo_port.setMinimumWidth(120)
        lay.addWidget(self._combo_port)
        btn_ref = QPushButton("Actualizar"); btn_ref.setFixedWidth(90)
        btn_ref.setStyleSheet(self._bs()); btn_ref.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_ref)
        lay.addWidget(QFrame()); lay.addStretch()
        self._btn_flash_maestro = QPushButton("Flashear Maestro")
        self._btn_flash_maestro.setFixedHeight(40); self._btn_flash_maestro.setFixedWidth(160)
        self._btn_flash_maestro.setStyleSheet(self._bs_primary())
        self._btn_flash_maestro.clicked.connect(lambda: self._iniciar_flash("maestro"))
        lay.addWidget(self._btn_flash_maestro)
        self._btn_flash_slave = QPushButton("Flashear Slave")
        self._btn_flash_slave.setFixedHeight(40); self._btn_flash_slave.setFixedWidth(160)
        self._btn_flash_slave.setStyleSheet(self._bs_primary())
        self._btn_flash_slave.clicked.connect(lambda: self._iniciar_flash("slave"))
        lay.addWidget(self._btn_flash_slave)
        return box

    def _build_output_section(self):
        box = QGroupBox("Output de esptool")
        box.setStyleSheet(self._gs(C_BLUE))
        lay = QVBoxLayout(box); lay.setSpacing(6)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100); self._progress.setValue(0)
        self._progress.setTextVisible(True); self._progress.setFixedHeight(20)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C_OVERLAY};border-radius:4px;border:none;"
            f"color:{C_TEXT};font-size:11px;}}"
            f"QProgressBar::chunk{{background:{C_BLUE};border-radius:4px;}}")
        lay.addWidget(self._progress)
        self._output = QTextEdit(); self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 10))
        self._output.setStyleSheet(
            f"QTextEdit{{background:{C_MANTLE};color:{C_GREEN};"
            f"border:1px solid {C_OVERLAY};border-radius:4px;}}")
        lay.addWidget(self._output, 1)
        bot = QHBoxLayout()
        self._lbl_status = QLabel("Listo.")
        self._lbl_status.setStyleSheet(f"color:{C_SUBTEXT};font-size:11px;")
        btn_cl = QPushButton("Limpiar"); btn_cl.setFixedWidth(80)
        btn_cl.setStyleSheet(self._bs()); btn_cl.clicked.connect(self._clear_output)
        bot.addWidget(self._lbl_status, 1); bot.addWidget(btn_cl)
        lay.addLayout(bot)
        return box

    # ── Lógica ───────────────────────────────────────────────
    def _refresh_ports(self):
        self._combo_port.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports: self._combo_port.addItem(p.device)
        if not ports: self._combo_port.addItem("(sin puertos)")

    def _refresh_bin_labels(self):
        admin = self._is_admin()
        for btn in (self._btn_bin_maestro, self._btn_bin_slave):
            btn.setEnabled(admin)

        # Maestro
        m_path = _get_bin_maestro()
        m_override = bool(_bin_maestro_override)
        m_exists = os.path.exists(m_path)
        tag = "[override]" if m_override else "[builtin]"
        color = C_GREEN if m_exists else C_RED
        self._lbl_maestro.setText(
            f"{os.path.basename(m_path)}  {tag}"
            if m_exists else f"{os.path.basename(m_path)}  NO ENCONTRADO")
        self._lbl_maestro.setStyleSheet(
            f"color:{color};font-size:11px;font-family:Consolas;")
        self._btn_reset_maestro.setEnabled(admin and m_override)

        # Slave
        s_path = _get_bin_slave()
        s_override = bool(_bin_slave_override)
        s_exists = os.path.exists(s_path)
        tag = "[override]" if s_override else "[builtin]"
        color = C_GREEN if s_exists else C_RED
        self._lbl_slave.setText(
            f"{os.path.basename(s_path)}  {tag}"
            if s_exists else f"{os.path.basename(s_path)}  NO ENCONTRADO")
        self._lbl_slave.setStyleSheet(
            f"color:{color};font-size:11px;font-family:Consolas;")
        self._btn_reset_slave.setEnabled(admin and s_override)

    def _elegir_bin(self, tipo: str):
        if not self._is_admin():
            QMessageBox.warning(self, "Sin permiso",
                "Solo el administrador puede cambiar los archivos de firmware.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, f"Override firmware {tipo} (.bin)",
            os.path.expanduser("~"), "Firmware ESP32 (*.bin)")
        if not path: return
        if tipo == "maestro": _set_bin_maestro(path)
        else:                 _set_bin_slave(path)
        self._refresh_bin_labels()
        self._log(f"Override {tipo}: {path}", C_YELLOW)
        self.status_msg.emit(f"Override {tipo}: {os.path.basename(path)}")

    def _restore_bin(self, tipo: str):
        if tipo == "maestro": _set_bin_maestro("")
        else:                 _set_bin_slave("")
        self._refresh_bin_labels()
        self._log(f"Firmware {tipo} restaurado al builtin.", C_GREEN)

    def _iniciar_flash(self, tipo: str):
        bin_path = _get_bin_maestro() if tipo == "maestro" else _get_bin_slave()
        if not os.path.exists(bin_path):
            builtin = _BUILTIN_MAESTRO if tipo == "maestro" else _BUILTIN_SLAVE
            QMessageBox.critical(self, "Archivo no encontrado",
                f"No se encontro el firmware para '{tipo}':\n{bin_path}\n\n"
                f"Compila el sketch en Arduino IDE.\n"
                f"Ruta esperada:\n{builtin}")
            return
        port = self._combo_port.currentText()
        if not port or port == "(sin puertos)":
            QMessageBox.warning(self, "Sin puerto", "Selecciona un puerto COM.")
            return
        reply = QMessageBox.question(self, "Confirmar flash",
            f"Flashear {tipo.upper()} en {port}?\n"
            f"Archivo: {os.path.basename(bin_path)}\n"
            f"Baud: {BAUD_RATE}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes: return
        self._set_flash_buttons(False)
        self._progress.setValue(0)
        self._log(f"\n--- Flash {tipo.upper()} en {port} ---", C_TEAL)
        self.status_msg.emit(f"Flasheando {tipo}...")
        self._worker = FlashWorker(port, bin_path, BAUD_RATE)
        self._worker.output.connect(self._on_output)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(lambda ok, msg: self._on_finished(ok, msg, tipo))
        self._worker.start()

    def _on_output(self, line: str):
        self._output.append(f'<span style="color:{C_GREEN}">{line}</span>')
        self._output.moveCursor(QTextCursor.End)

    def _on_finished(self, success: bool, msg: str, tipo: str):
        color = C_GREEN if success else C_RED
        self._log(f"\n{msg}", color)
        self._lbl_status.setText(msg)
        self._lbl_status.setStyleSheet(f"color:{color};font-size:11px;")
        self._set_flash_buttons(True)
        self.status_msg.emit(f"Flash {tipo} {'OK' if success else 'FALLIDO'}: {msg}")

    def _set_flash_buttons(self, enabled: bool):
        self._btn_flash_maestro.setEnabled(enabled)
        self._btn_flash_slave.setEnabled(enabled)

    def _clear_output(self):
        self._output.clear(); self._progress.setValue(0)
        self._lbl_status.setText("Listo.")
        self._lbl_status.setStyleSheet(f"color:{C_SUBTEXT};font-size:11px;")

    def _log(self, msg: str, color: str = None):
        color = color or C_TEXT
        ts = datetime.now().strftime("%H:%M:%S")
        self._output.append(
            f'<span style="color:{C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>')
        self._output.moveCursor(QTextCursor.End)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate(); self._worker.wait()

    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text); l.setStyleSheet(f"color:{C_TEXT};font-weight:600;")
        return l

    def _gs(self, accent: str) -> str:
        return (f"QGroupBox{{border:1px solid {C_OVERLAY};border-radius:8px;"
                f"margin-top:10px;font-weight:bold;color:{accent};padding:10px;}}"
                f"QGroupBox::title{{subcontrol-origin:margin;left:10px;padding:0 6px;}}")

    def _bs(self) -> str:
        return (f"QPushButton{{background:{C_SURFACE};color:{C_TEXT};"
                f"border:1px solid {C_OVERLAY};border-radius:5px;"
                f"font-size:12px;padding:4px 10px;}}"
                f"QPushButton:hover{{background:{C_OVERLAY};}}"
                f"QPushButton:disabled{{background:{C_MANTLE};color:{C_OVERLAY};}}")

    def _bs_primary(self) -> str:
        return (f"QPushButton{{background:#2563eb;color:white;border:none;"
                f"border-radius:5px;font-size:13px;font-weight:700;}}"
                f"QPushButton:hover{{background:#1d4ed8;}}"
                f"QPushButton:disabled{{background:#1e3a6e;color:#7a9fd6;}}")