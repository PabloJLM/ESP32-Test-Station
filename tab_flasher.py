import os
import re
import subprocess
import serial.tools.list_ports
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QLineEdit, QTextEdit, QProgressBar, QFileDialog,
    QMessageBox, QFrame,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor


# ══════════════════════════════════════════════════════════════
#  CONFIGURACION
# ══════════════════════════════════════════════════════════════

BAUD_RATE    = 115200
FLASH_OFFSET = "0x0"       # offset de escritura para ESP32


# ══════════════════════════════════════════════════════════════
#  ALMACENAMIENTO DE RUTAS DE BINARIOS
#  El admin las fija; persisten mientras corre la app.
# ══════════════════════════════════════════════════════════════

_bin_maestro = ""
_bin_slave   = ""


def get_bin_maestro() -> str:
    return _bin_maestro

def get_bin_slave() -> str:
    return _bin_slave

def set_bin_maestro(path: str):
    global _bin_maestro
    _bin_maestro = path

def set_bin_slave(path: str):
    global _bin_slave
    _bin_slave = path


# ══════════════════════════════════════════════════════════════
#  HILO DE FLASHEO
# ══════════════════════════════════════════════════════════════

class FlashWorker(QThread):
    output   = pyqtSignal(str)       # linea de texto del proceso
    progress = pyqtSignal(int)       # 0-100
    finished = pyqtSignal(bool, str) # (exito, mensaje final)

    def __init__(self, port: str, bin_path: str, baud: int = BAUD_RATE):
        super().__init__()
        self.port     = port
        self.bin_path = bin_path
        self.baud     = baud

    def run(self):
        import sys
        # Usar el mismo Python de la app para garantizar que esptool este disponible
        cmd = [
            sys.executable, "-m", "esptool",
            "--chip",  "esp32",
            "--port",  self.port,
            "--baud",  str(self.baud),
            "write_flash",
            FLASH_OFFSET,
            self.bin_path,
        ]
        self.output.emit(f"Ejecutando: {' '.join(cmd)}\n")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in proc.stdout:
                line = line.rstrip()
                self.output.emit(line)
                # Detectar porcentaje en la salida de esptool
                # Formato tipico: "Writing at 0x00010000... (12 %)"
                m = re.search(r'\((\d+)\s*%\)', line)
                if m:
                    self.progress.emit(int(m.group(1)))

            proc.wait()
            if proc.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Flash completado exitosamente.")
            else:
                self.finished.emit(False, f"esptool termino con codigo {proc.returncode}.")

        except FileNotFoundError:
            self.finished.emit(
                False,
                "esptool no encontrado.\nVerificar: python -m esptool version\nInstalar: pip install esptool"
            )
        except Exception as e:
            self.finished.emit(False, str(e))


# ══════════════════════════════════════════════════════════════
#  PESTANA FLASHER
# ══════════════════════════════════════════════════════════════

class TabFlasher(QWidget):
    status_msg = pyqtSignal(str)

    # Colores Catppuccin Mocha
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

    def __init__(self, is_admin_fn=None):
        super().__init__()
        # Funcion que devuelve True si el usuario activo es admin
        self._is_admin = is_admin_fn or (lambda: False)
        self._worker   = None
        self._build_ui()
        self._refresh_ports()

    def notify_login(self):
        # Llamar desde esp32_tester cuando cambia la sesion
        self._refresh_bin_labels()

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        root.addWidget(self._build_bin_section())
        root.addWidget(self._build_flash_section())
        root.addWidget(self._build_output_section(), 1)

    def _build_bin_section(self):
        box = QGroupBox("Archivos de firmware (.bin)")
        box.setStyleSheet(self._group_style(self.C_BLUE))
        grid = QGridLayout(box)
        grid.setSpacing(10)

        # Maestro
        grid.addWidget(self._lbl("Maestro:"), 0, 0)
        self._lbl_maestro = QLabel("Sin seleccionar")
        self._lbl_maestro.setStyleSheet(
            f"color:{self.C_YELLOW}; font-size:11px; font-family:Consolas;"
        )
        self._lbl_maestro.setWordWrap(True)
        grid.addWidget(self._lbl_maestro, 0, 1)
        self._btn_bin_maestro = QPushButton("Elegir .bin")
        self._btn_bin_maestro.setFixedWidth(110)
        self._btn_bin_maestro.setStyleSheet(self._btn_style_normal())
        self._btn_bin_maestro.clicked.connect(lambda: self._elegir_bin("maestro"))
        grid.addWidget(self._btn_bin_maestro, 0, 2)

        # Slave
        grid.addWidget(self._lbl("Slave:"), 1, 0)
        self._lbl_slave = QLabel("Sin seleccionar")
        self._lbl_slave.setStyleSheet(
            f"color:{self.C_YELLOW}; font-size:11px; font-family:Consolas;"
        )
        self._lbl_slave.setWordWrap(True)
        grid.addWidget(self._lbl_slave, 1, 1)
        self._btn_bin_slave = QPushButton("Elegir .bin")
        self._btn_bin_slave.setFixedWidth(110)
        self._btn_bin_slave.setStyleSheet(self._btn_style_normal())
        self._btn_bin_slave.clicked.connect(lambda: self._elegir_bin("slave"))
        grid.addWidget(self._btn_bin_slave, 1, 2)

        grid.setColumnStretch(1, 1)
        self._refresh_bin_labels()
        return box

    def _build_flash_section(self):
        box = QGroupBox("Flashear")
        box.setStyleSheet(self._group_style(self.C_TEAL))
        lay = QHBoxLayout(box)
        lay.setSpacing(14)

        # Puerto
        lay.addWidget(self._lbl("Puerto:"))
        self._combo_port = QComboBox()
        self._combo_port.setMinimumWidth(120)
        lay.addWidget(self._combo_port)

        btn_refresh = QPushButton("Actualizar")
        btn_refresh.setFixedWidth(90)
        btn_refresh.setStyleSheet(self._btn_style_normal())
        btn_refresh.clicked.connect(self._refresh_ports)
        lay.addWidget(btn_refresh)

        lay.addWidget(QFrame())  # separador visual
        lay.addStretch()

        # Botones de flash
        self._btn_flash_maestro = QPushButton("Flashear Maestro")
        self._btn_flash_maestro.setFixedHeight(40)
        self._btn_flash_maestro.setFixedWidth(160)
        self._btn_flash_maestro.setStyleSheet(self._btn_style_primary())
        self._btn_flash_maestro.clicked.connect(lambda: self._iniciar_flash("maestro"))
        lay.addWidget(self._btn_flash_maestro)

        self._btn_flash_slave = QPushButton("Flashear Slave")
        self._btn_flash_slave.setFixedHeight(40)
        self._btn_flash_slave.setFixedWidth(160)
        self._btn_flash_slave.setStyleSheet(self._btn_style_primary())
        self._btn_flash_slave.clicked.connect(lambda: self._iniciar_flash("slave"))
        lay.addWidget(self._btn_flash_slave)

        return box

    def _build_output_section(self):
        box = QGroupBox("Output de esptool")
        box.setStyleSheet(self._group_style(self.C_BLUE))
        lay = QVBoxLayout(box)
        lay.setSpacing(6)

        # Barra de progreso
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(20)
        self._progress.setStyleSheet(f"""
            QProgressBar {{
                background: {self.C_OVERLAY};
                border-radius: 4px;
                border: none;
                color: {self.C_TEXT};
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background: {self.C_BLUE};
                border-radius: 4px;
            }}
        """)
        lay.addWidget(self._progress)

        # Terminal de output
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Consolas", 10))
        self._output.setStyleSheet(f"""
            QTextEdit {{
                background: {self.C_MANTLE};
                color: {self.C_GREEN};
                border: 1px solid {self.C_OVERLAY};
                border-radius: 4px;
            }}
        """)
        lay.addWidget(self._output, 1)

        # Fila inferior con estado y boton limpiar
        bot = QHBoxLayout()
        self._lbl_status_flash = QLabel("Listo.")
        self._lbl_status_flash.setStyleSheet(f"color:{self.C_SUBTEXT}; font-size:11px;")
        btn_cl = QPushButton("Limpiar")
        btn_cl.setFixedWidth(80)
        btn_cl.setStyleSheet(self._btn_style_normal())
        btn_cl.clicked.connect(self._clear_output)
        bot.addWidget(self._lbl_status_flash, 1)
        bot.addWidget(btn_cl)
        lay.addLayout(bot)

        return box

    # ── Logica ───────────────────────────────────────────────────
    def _refresh_ports(self):
        self._combo_port.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self._combo_port.addItem(p.device)
        if not ports:
            self._combo_port.addItem("(sin puertos)")

    def _refresh_bin_labels(self):
        # Habilita o deshabilita los botones segun nivel de usuario
        admin = self._is_admin()
        self._btn_bin_maestro.setEnabled(admin)
        self._btn_bin_slave.setEnabled(admin)

        # Actualiza etiquetas con rutas actuales
        m = get_bin_maestro()
        s = get_bin_slave()
        self._lbl_maestro.setText(
            os.path.basename(m) if m else "Sin seleccionar"
        )
        self._lbl_maestro.setStyleSheet(
            f"color:{self.C_GREEN if m else self.C_YELLOW}; "
            f"font-size:11px; font-family:Consolas;"
        )
        self._lbl_slave.setText(
            os.path.basename(s) if s else "Sin seleccionar"
        )
        self._lbl_slave.setStyleSheet(
            f"color:{self.C_GREEN if s else self.C_YELLOW}; "
            f"font-size:11px; font-family:Consolas;"
        )

    def _elegir_bin(self, tipo: str):
        if not self._is_admin():
            QMessageBox.warning(self, "Sin permiso",
                "Solo el administrador puede cambiar los archivos de firmware.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Seleccionar firmware {tipo} (.bin)",
            os.path.expanduser("~"),
            "Firmware ESP32 (*.bin)"
        )
        if not path:
            return
        if tipo == "maestro":
            set_bin_maestro(path)
        else:
            set_bin_slave(path)
        self._refresh_bin_labels()
        self._log(f"Firmware {tipo} configurado: {path}", self.C_GREEN)
        self.status_msg.emit(f"Firmware {tipo} listo: {os.path.basename(path)}")

    def _iniciar_flash(self, tipo: str):
        # Verificar que hay bin seleccionado
        bin_path = get_bin_maestro() if tipo == "maestro" else get_bin_slave()
        if not bin_path:
            QMessageBox.warning(
                self, "Firmware no configurado",
                f"El admin debe seleccionar el archivo .bin del {tipo} antes de flashear."
            )
            return
        if not os.path.exists(bin_path):
            QMessageBox.critical(
                self, "Archivo no encontrado",
                f"El archivo ya no existe en:\n{bin_path}\n\nEl admin debe seleccionarlo de nuevo."
            )
            return

        port = self._combo_port.currentText()
        if not port or port == "(sin puertos)":
            QMessageBox.warning(self, "Sin puerto",
                "Selecciona un puerto COM antes de flashear.")
            return

        reply = QMessageBox.question(
            self, "Confirmar flash",
            f"Flashear firmware {tipo.upper()} en {port}?\n\n"
            f"Archivo: {os.path.basename(bin_path)}\n"
            f"Baud: {BAUD_RATE}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._set_flash_buttons(False)
        self._progress.setValue(0)
        self._progress.setStyleSheet(self._progress.styleSheet().replace(
            self.C_RED, self.C_BLUE
        ).replace(self.C_GREEN, self.C_BLUE))
        self._log(f"\n--- Iniciando flash {tipo.upper()} en {port} ---", self.C_TEAL)
        self.status_msg.emit(f"Flasheando {tipo}...")

        self._worker = FlashWorker(port, bin_path, BAUD_RATE)
        self._worker.output.connect(self._on_output)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.finished.connect(lambda ok, msg: self._on_finished(ok, msg, tipo))
        self._worker.start()

    def _on_output(self, line: str):
        self._output.append(
            f'<span style="color:{self.C_GREEN}">{line}</span>'
        )
        self._output.moveCursor(QTextCursor.End)

    def _on_finished(self, success: bool, msg: str, tipo: str):
        color = self.C_GREEN if success else self.C_RED
        self._log(f"\n{msg}", color)
        self._lbl_status_flash.setText(msg)
        self._lbl_status_flash.setStyleSheet(f"color:{color}; font-size:11px;")

        # Cambiar color de la barra segun resultado
        chunk_color = self.C_GREEN if success else self.C_RED
        self._progress.setStyleSheet(
            self._progress.styleSheet().replace(self.C_BLUE, chunk_color)
        )
        if not success:
            self._progress.setValue(0)

        self._set_flash_buttons(True)
        self.status_msg.emit(
            f"Flash {tipo} {'OK' if success else 'FALLIDO'}: {msg}"
        )

    def _set_flash_buttons(self, enabled: bool):
        self._btn_flash_maestro.setEnabled(enabled)
        self._btn_flash_slave.setEnabled(enabled)

    def _clear_output(self):
        self._output.clear()
        self._progress.setValue(0)
        self._lbl_status_flash.setText("Listo.")
        self._lbl_status_flash.setStyleSheet(
            f"color:{self.C_SUBTEXT}; font-size:11px;"
        )

    def _log(self, msg: str, color: str = None):
        color = color or self.C_TEXT
        ts = datetime.now().strftime("%H:%M:%S")
        self._output.append(
            f'<span style="color:{self.C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )
        self._output.moveCursor(QTextCursor.End)

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait()

    # ── Helpers de estilo ────────────────────────────────────────
    def _lbl(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{self.C_TEXT}; font-weight:600;")
        return l

    def _group_style(self, accent: str) -> str:
        return (
            f"QGroupBox {{ border:1px solid {self.C_OVERLAY}; border-radius:8px; "
            f"margin-top:10px; font-weight:bold; color:{accent}; padding:10px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 6px; }}"
        )

    def _btn_style_normal(self) -> str:
        return (
            f"QPushButton {{ background:{self.C_SURFACE}; color:{self.C_TEXT}; "
            f"border:1px solid {self.C_OVERLAY}; border-radius:5px; "
            f"font-size:12px; padding:4px 10px; }}"
            f"QPushButton:hover {{ background:{self.C_OVERLAY}; }}"
            f"QPushButton:disabled {{ background:{self.C_MANTLE}; color:{self.C_OVERLAY}; }}"
        )

    def _btn_style_primary(self) -> str:
        return (
            f"QPushButton {{ background:#2563eb; color:white; border:none; "
            f"border-radius:5px; font-size:13px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#1d4ed8; }}"
            f"QPushButton:disabled {{ background:#1e3a6e; color:#7a9fd6; }}"
        )
