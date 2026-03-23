import os
import sys
import shutil
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QLineEdit,
    QCheckBox, QMessageBox, QFrame, QStackedWidget,
    QTextEdit, QSizePolicy, QSlider, QFileDialog,
    QComboBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from validacion import (
    get_current_reports_root,
    reset_reports_root,
    _ask_reports_root,
)


def _resource_path(relative: str) -> str:
    # Resuelve rutas para .py y para .exe generado con PyInstaller
    #ni idea de como funciona xd
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


USERS = {
    "admin1": "balam2026",
    "admin2": "balam2026",
    "admin3": "balam2026",
    "admin4": "balam2026",
}

EASTER_USER = "".join([chr(x) for x in [74, 111, 74, 111, 80, 74]])
EASTER_PASS = "".join([chr(x) for x in [89, 97, 110, 105, 114, 97]])

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

CAT_COLORS = {
    "ESP32":       C_BLUE,
    "Robofut":     C_MAUVE,
    "Todoterreno": C_TEAL,
    "STEM SR":     C_PEACH,
    "STEM JR":     C_YELLOW,
    "Drones":      "#89dceb",
    "IOT":         C_GREEN,
}

FOTO1_TEXTO = "Hola"
FOTO2_TEXTO = "Adios"

VIDEO_PATH = _resource_path(os.path.join("imgs", "reze.mp4"))
FOTO1_PATH = _resource_path(os.path.join("imgs", "easter_egg3.jpeg"))
FOTO2_PATH = _resource_path(os.path.join("imgs", "easter_egg2.jpeg"))


class ClearWorker(QThread):
    progress = pyqtSignal(str, bool)
    finished = pyqtSignal()

    def __init__(self, sheet_id, sheet_map, targets, header_row=1):
        super().__init__()
        self.sheet_id   = sheet_id
        self.sheet_map  = sheet_map
        self.targets    = targets
        self.header_row = header_row

    def run(self):
        try:
            import gspread
            gc   = gspread.oauth(
                credentials_filename='credentials.json',
                authorized_user_filename='token.json'
            )
            book = gc.open_by_key(self.sheet_id)
            for sheet_name in self.targets:
                try:
                    ws        = book.worksheet(sheet_name)
                    all_vals  = ws.get_all_values()
                    data_rows = len(all_vals) - self.header_row
                    if data_rows <= 0:
                        self.progress.emit(f"{sheet_name}: ya estaba vacia.", False)
                        continue
                    start = self.header_row + 1
                    end   = len(all_vals)
                    ws.batch_clear([f"A{start}:E{end}"])
                    for row in range(start, end + 1):
                        try:
                            ws.format(f"A{row}", {
                                "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                            })
                        except Exception:
                            pass
                    self.progress.emit(f"{sheet_name}: {data_rows} fila(s) borradas.", False)
                except Exception as e:
                    self.progress.emit(f"{sheet_name}: ERROR — {e}", True)
        except FileNotFoundError:
            self.progress.emit("credentials.json / token.json no encontrado.", True)
        except Exception as e:
            self.progress.emit(f"Error de conexion: {e}", True)
        self.finished.emit()


class PhotoWidget(QWidget):
    def __init__(self, filepath: str, texto: str):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lbl_txt = QLabel(texto)
        lbl_txt.setFont(QFont("Segoe UI", 18, QFont.Bold))
        lbl_txt.setAlignment(Qt.AlignCenter)
        lbl_txt.setWordWrap(True)
        lbl_txt.setStyleSheet(
            f"color:{C_MAUVE}; background:rgba(30,30,46,180); border-radius:8px; padding:6px 18px;"
        )
        lay.addWidget(lbl_txt)
        lbl_img = QLabel()
        lbl_img.setAlignment(Qt.AlignCenter)
        lbl_img.setStyleSheet("background:transparent;")
        if os.path.exists(filepath):
            from PyQt5.QtGui import QPixmap
            pix = QPixmap(filepath).scaled(560, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            lbl_img.setPixmap(pix)
        else:
            lbl_img.setText(f"[ imagen no encontrada ]\n{filepath}")
            lbl_img.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        lay.addWidget(lbl_img, 1)


class VideoWidget(QWidget):
    def __init__(self, filepath: str):
        super().__init__()
        self.setStyleSheet("background:black;")
        self._filepath = filepath
        self._ready    = False
        try:
            import vlc
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(4)
            self._frame = QFrame()
            self._frame.setStyleSheet("background:black;")
            self._frame.setMinimumHeight(300)
            lay.addWidget(self._frame, 1)
            ctrl = QHBoxLayout()
            ctrl.setSpacing(8)
            self._btn_play = QPushButton("Play")
            self._btn_play.setFixedSize(52, 28)
            self._btn_play.setStyleSheet(
                f"QPushButton {{ background:{C_SURFACE}; color:{C_TEXT}; "
                f"border:1px solid {C_OVERLAY}; border-radius:4px; font-size:11px; }}"
                f"QPushButton:hover {{ background:{C_OVERLAY}; }}"
            )
            self._btn_play.clicked.connect(self._toggle_play)
            self._slider = QSlider(Qt.Horizontal)
            self._slider.setRange(0, 1000)
            self._slider.setStyleSheet(
                f"QSlider::groove:horizontal {{ height:4px; background:{C_OVERLAY}; border-radius:2px; }}"
                f"QSlider::handle:horizontal {{ background:{C_MAUVE}; width:12px; height:12px; "
                f"margin:-4px 0; border-radius:6px; }}"
                f"QSlider::sub-page:horizontal {{ background:{C_MAUVE}; border-radius:2px; }}"
            )
            self._slider.sliderMoved.connect(self._seek)
            self._lbl_time = QLabel("0:00 / 0:00")
            self._lbl_time.setStyleSheet(f"color:{C_SUBTEXT}; font-size:10px;")
            self._lbl_time.setFixedWidth(90)
            self._lbl_time.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ctrl.addWidget(self._btn_play)
            ctrl.addWidget(self._slider, 1)
            ctrl.addWidget(self._lbl_time)
            lay.addLayout(ctrl)
            self._instance = vlc.Instance("--no-xlib", "--quiet")
            self._media    = self._instance.media_new(self._filepath)
            self._player   = self._instance.media_player_new()
            self._player.set_media(self._media)
            wid = int(self._frame.winId())
            if hasattr(self._player, 'set_hwnd'):       self._player.set_hwnd(wid)
            elif hasattr(self._player, 'set_xwindow'):  self._player.set_xwindow(wid)
            elif hasattr(self._player, 'set_nsobject'): self._player.set_nsobject(wid)
            self._timer = QTimer(self)
            self._timer.setInterval(500)
            self._timer.timeout.connect(self._tick)
            self._ready = True
        except ImportError:
            lay = QVBoxLayout(self)
            lbl = QLabel("python-vlc no disponible.\n1. Instala VLC desde videolan.org\n2. pip install python-vlc")
            lbl.setStyleSheet(f"color:{C_RED}; background:{C_MANTLE}; padding:20px; font-size:12px;")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

    def play(self):
        if self._ready:
            self._player.play(); self._timer.start(); self._btn_play.setText("Pausa")

    def stop(self):
        if self._ready:
            self._player.stop(); self._timer.stop()
            self._btn_play.setText("Play"); self._slider.setValue(0)
            self._lbl_time.setText("0:00 / 0:00")

    def release(self):
        if self._ready:
            self._timer.stop(); self._player.stop()
            self._player.release(); self._media.release(); self._instance.release()
            self._ready = False

    def _toggle_play(self):
        if not self._ready: return
        if self._player.is_playing():
            self._player.pause(); self._btn_play.setText("Play"); self._timer.stop()
        else:
            self._player.play(); self._btn_play.setText("Pausa"); self._timer.start()

    def _seek(self, val):
        if self._ready: self._player.set_position(val / 1000.0)

    def _tick(self):
        if not self._ready: return
        pos = self._player.get_position()
        dur = self._player.get_length()
        cur = self._player.get_time()
        self._slider.blockSignals(True)
        self._slider.setValue(int(pos * 1000))
        self._slider.blockSignals(False)
        self._lbl_time.setText(f"{self._fmt(cur)} / {self._fmt(dur)}")

    @staticmethod
    def _fmt(ms):
        if ms < 0: return "0:00"
        s = ms // 1000
        return f"{s // 60}:{s % 60:02d}"


# easter egg!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
class EasterEggDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet(f"background:{C_MANTLE};")
        self.setFixedSize(640, 540)
        self._build_ui()
        self._center()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)
        lbl = QLabel("Hecho por JoJoPJ")
        lbl.setFont(QFont("Segoe UI", 15, QFont.Bold))
        lbl.setStyleSheet(f"color:{C_MAUVE}; background:transparent;")
        lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(lbl)
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._video_widget = VideoWidget(VIDEO_PATH)
        self._img1 = PhotoWidget(FOTO1_PATH, FOTO1_TEXTO)
        self._img2 = PhotoWidget(FOTO2_PATH, FOTO2_TEXTO)
        self._stack.addWidget(self._video_widget)
        self._stack.addWidget(self._img1)
        self._stack.addWidget(self._img2)
        root.addWidget(self._stack, 1)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        s_active = (
            f"QPushButton {{ background:#2563eb; color:white; border:none; border-radius:6px; "
            f"font-size:12px; font-weight:700; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:#1d4ed8; }}"
        )
        s_normal = (
            f"QPushButton {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid {C_OVERLAY}; "
            f"border-radius:6px; font-size:12px; font-weight:600; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:{C_OVERLAY}; }}"
        )
        self._btns = []
        for i, label in enumerate(["Video", "Foto 1", "Foto 2"]):
            b = QPushButton(label)
            b.setFixedHeight(32)
            b.setStyleSheet(s_active if i == 0 else s_normal)
            b.clicked.connect(lambda _, x=i: self._switch(x))
            btn_row.addWidget(b)
            self._btns.append((b, s_active, s_normal))
        btn_row.addStretch()
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setFixedHeight(32); btn_cerrar.setFixedWidth(90)
        btn_cerrar.setStyleSheet(
            f"QPushButton {{ background:#7f1d1d; color:{C_RED}; border:1px solid #ef4444; "
            f"border-radius:6px; font-size:12px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#991b1b; }}"
        )
        btn_cerrar.clicked.connect(self._cerrar)
        btn_row.addWidget(btn_cerrar)
        root.addLayout(btn_row)

    def _switch(self, idx):
        if self._stack.currentIndex() == 0 and idx != 0:
            self._video_widget.stop()
        if idx == 0:
            self._video_widget.play()
        self._stack.setCurrentIndex(idx)
        for i, (btn, a, n) in enumerate(self._btns):
            btn.setStyleSheet(a if i == idx else n)

    def _center(self):
        from PyQt5.QtWidgets import QDesktopWidget
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp); self.move(qr.topLeft())

    def _cerrar(self):
        self._video_widget.release(); self.close()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(400, self._video_widget.play)

    def closeEvent(self, event):
        self._video_widget.release(); super().closeEvent(event)


class LoginWidget(QWidget):
    login_ok = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._attempts = 0
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setFixedWidth(340)
        card.setStyleSheet(
            f"QFrame {{ background:{C_SURFACE}; border:1px solid {C_OVERLAY}; border-radius:12px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)
        title = QLabel("Acceso Administrador")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet(f"color:{C_BLUE}; background:transparent; border:none;")
        title.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background:{C_OVERLAY}; max-height:1px; border:none;")
        lay.addWidget(sep)
        for attr, label_txt, placeholder, echo in [
            ("input_user", "Usuario",    "Ingresa tu usuario",    QLineEdit.Normal),
            ("input_pass", "Contrasena", "Ingresa tu contrasena", QLineEdit.Password),
        ]:
            lbl = QLabel(label_txt)
            lbl.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px; background:transparent; border:none;")
            lay.addWidget(lbl)
            field = QLineEdit()
            field.setPlaceholderText(placeholder)
            field.setEchoMode(echo)
            field.setFixedHeight(36)
            field.returnPressed.connect(self._do_login)
            setattr(self, attr, field)
            lay.addWidget(field)
        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet(
            f"color:{C_RED}; font-size:11px; background:transparent; border:none;"
        )
        self.lbl_error.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.lbl_error)
        self.btn_login = QPushButton("Entrar")
        self.btn_login.setFixedHeight(38)
        self.btn_login.setStyleSheet(
            f"QPushButton {{ background:#2563eb; color:white; border:none; border-radius:6px; "
            f"font-size:13px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#1d4ed8; }}"
        )
        self.btn_login.clicked.connect(self._do_login)
        lay.addWidget(self.btn_login)
        outer.addWidget(card)

    def _do_login(self):
        user = self.input_user.text().strip()
        pwd  = self.input_pass.text()
        if user == EASTER_USER and pwd == EASTER_PASS:
            self.input_pass.clear(); self.lbl_error.setText("")
            self._egg = EasterEggDialog(self); self._egg.show()
            return
        if USERS.get(user) == pwd:
            self.lbl_error.setText(""); self.input_pass.clear()
            self.login_ok.emit(user)
        else:
            self._attempts += 1
            self.lbl_error.setText(
                f"Usuario o contrasena incorrectos.  (intento {self._attempts})"
            )
            self.input_pass.clear(); self.input_pass.setFocus()

    def reset(self):
        self.input_user.clear(); self.input_pass.clear()
        self.lbl_error.setText(""); self._attempts = 0

class AdminPanel(QWidget):
    logout = pyqtSignal()

    def __init__(self, sheet_id, sheet_map, header_row=1):
        super().__init__()
        self.sheet_id   = sheet_id
        self.sheet_map  = sheet_map
        self.header_row = header_row
        self._worker    = None
        self._checks    = {}
        self._build_ui()

    def set_user(self, username: str):
        self.lbl_user.setText(f"Sesion activa: {username}")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 14, 16, 14)
        top = QHBoxLayout()
        self.lbl_user = QLabel("Sesion: —")
        self.lbl_user.setStyleSheet(f"color:{C_TEAL}; font-size:12px; font-weight:600;")
        top.addWidget(self.lbl_user)
        top.addStretch()
        btn_logout = QPushButton("Cerrar sesion")
        btn_logout.setFixedWidth(130)
        btn_logout.setStyleSheet(
            f"QPushButton {{ background:{C_SURFACE}; color:{C_RED}; border:1px solid {C_RED}; "
            f"border-radius:5px; font-size:12px; font-weight:600; padding:4px 10px; }}"
            f"QPushButton:hover {{ background:#3b1a1a; }}"
        )
        btn_logout.clicked.connect(self.logout.emit)
        top.addWidget(btn_logout)
        root.addLayout(top)
        root.addWidget(self._build_selector())
        root.addWidget(self._build_reports_section())
        root.addWidget(self._build_log(), 1)
        root.addWidget(self._build_action_bar())

    def _build_selector(self):
        box = QGroupBox("Seleccionar hojas a limpiar")
        box.setStyleSheet(
            f"QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:8px; margin-top:10px; "
            f"font-weight:bold; color:{C_RED}; padding:10px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 6px; }}"
        )
        outer = QVBoxLayout(box)
        warn = QLabel(
            "Esta accion borra TODOS los registros de las hojas seleccionadas. No se puede deshacer."
        )
        warn.setStyleSheet(
            f"color:{C_YELLOW}; font-size:11px; background:#2a2010; "
            f"border:1px solid #5a4a10; border-radius:6px; padding:8px 12px;"
        )
        warn.setWordWrap(True)
        outer.addWidget(warn)
        grid = QGridLayout(); grid.setSpacing(10)
        for i, name in enumerate(self.sheet_map.values()):
            color = CAT_COLORS.get(name, C_TEXT)
            cb    = QCheckBox(name)
            cb.setStyleSheet(
                f"QCheckBox {{ color:{color}; font-size:13px; font-weight:600; "
                f"spacing:8px; background:transparent; }}"
                f"QCheckBox::indicator {{ width:18px; height:18px; border:2px solid {color}; "
                f"border-radius:4px; background:{C_SURFACE}; }}"
                f"QCheckBox::indicator:checked {{ background:{color}; border:2px solid {color}; }}"
            )
            self._checks[name] = cb
            grid.addWidget(cb, i // 4, i % 4)
        outer.addLayout(grid)
        quick = QHBoxLayout()
        for label, checked in [("Seleccionar todas", True), ("Deseleccionar todas", False)]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setStyleSheet(
                f"QPushButton {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid {C_OVERLAY}; "
                f"border-radius:4px; font-size:11px; padding:2px 10px; }}"
                f"QPushButton:hover {{ background:{C_OVERLAY}; }}"
            )
            val = checked
            btn.clicked.connect(lambda _, v=val: [cb.setChecked(v) for cb in self._checks.values()])
            quick.addWidget(btn)
        quick.addStretch()
        outer.addLayout(quick)
        return box

    def _build_reports_section(self):
        # Seccion para gestionar la carpeta raiz de reportes PDF
        box = QGroupBox("Reportes PDF — Carpeta Local")
        box.setStyleSheet(
            f"QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:8px; margin-top:10px; "
            f"font-weight:bold; color:{C_BLUE}; padding:10px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 6px; }}"
        )
        outer = QVBoxLayout(box)
        outer.setSpacing(10)

        row_info = QHBoxLayout()
        lbl = QLabel("Carpeta raiz:")
        lbl.setFixedWidth(100)
        lbl.setStyleSheet(f"color:{C_TEXT}; font-weight:600;")
        self._lbl_root = QLabel("No configurada — se pedira al primer reporte.")
        self._lbl_root.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        self._lbl_root.setWordWrap(True)
        row_info.addWidget(lbl)
        row_info.addWidget(self._lbl_root, 1)
        outer.addLayout(row_info)

        btn_row = QHBoxLayout()

        btn_cambiar = QPushButton("Cambiar carpeta raiz")
        btn_cambiar.setFixedHeight(32)
        btn_cambiar.setStyleSheet(
            f"QPushButton {{ background:#2563eb; color:white; border:none; "
            f"border-radius:5px; font-size:12px; font-weight:700; padding:4px 14px; }}"
            f"QPushButton:hover {{ background:#1d4ed8; }}"
        )
        btn_cambiar.clicked.connect(self._cambiar_carpeta_raiz)

        btn_abrir = QPushButton("Abrir carpeta")
        btn_abrir.setFixedHeight(32)
        btn_abrir.setStyleSheet(
            f"QPushButton {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid {C_OVERLAY}; "
            f"border-radius:5px; font-size:12px; padding:4px 14px; }}"
            f"QPushButton:hover {{ background:{C_OVERLAY}; }}"
        )
        btn_abrir.clicked.connect(self._abrir_carpeta_raiz)

        btn_row.addWidget(btn_cambiar)
        btn_row.addWidget(btn_abrir)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        clean_row = QHBoxLayout()
        lbl_cat = QLabel("Limpiar categoria:")
        lbl_cat.setStyleSheet(f"color:{C_TEXT}; font-weight:600;")
        self._combo_cat = QComboBox()
        self._combo_cat.addItem("Todas las categorias")
        # Agrega cada categoria del sheet_map si esta disponible
        self._combo_cat.setStyleSheet(
            f"QComboBox {{ background:{C_SURFACE}; color:{C_TEXT}; border:1px solid {C_OVERLAY}; "
            f"border-radius:4px; padding:4px 8px; }}"
        )
        self._lbl_count = QLabel("")
        self._lbl_count.setStyleSheet(f"color:{C_SUBTEXT}; font-size:11px;")
        btn_limpiar = QPushButton("Limpiar")
        btn_limpiar.setFixedHeight(32)
        btn_limpiar.setFixedWidth(90)
        btn_limpiar.setStyleSheet(
            f"QPushButton {{ background:#7f1d1d; color:{C_RED}; border:1px solid #ef4444; "
            f"border-radius:5px; font-size:12px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#991b1b; }}"
        )
        btn_limpiar.clicked.connect(self._limpiar_reportes)
        clean_row.addWidget(lbl_cat)
        clean_row.addWidget(self._combo_cat)
        clean_row.addWidget(self._lbl_count, 1)
        clean_row.addWidget(btn_limpiar)
        outer.addLayout(clean_row)

        self._refresh_reports_ui()
        return box

    def _set_combo_categorias(self, root: str):
        # Rellena el combo con las subcarpetas existentes dentro de la raiz
        self._combo_cat.clear()
        self._combo_cat.addItem("Todas las categorias")
        if root and os.path.isdir(root):
            for name in sorted(os.listdir(root)):
                if os.path.isdir(os.path.join(root, name)):
                    self._combo_cat.addItem(name)

    def _refresh_reports_ui(self):
        # Actualiza la etiqueta de ruta y el conteo de PDFs
        root = get_current_reports_root()
        if root:
            self._lbl_root.setText(root)
            self._set_combo_categorias(root)
            self._update_count()
        else:
            self._lbl_root.setText("No configurada — se pedira al primer reporte.")
            self._lbl_count.setText("")

    def _update_count(self):
        root = get_current_reports_root()
        if not root or not os.path.isdir(root):
            self._lbl_count.setText("")
            return
        cat = self._combo_cat.currentText()
        if cat == "Todas las categorias":
            count = sum(
                len([f for f in os.listdir(os.path.join(root, d)) if f.endswith(".pdf")])
                for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))
            )
        else:
            path  = os.path.join(root, cat)
            count = len([f for f in os.listdir(path) if f.endswith(".pdf")]) if os.path.isdir(path) else 0
        self._lbl_count.setText(f"{count} PDF(s)")

    def _cambiar_carpeta_raiz(self):
        reset_reports_root()
        nueva = _ask_reports_root(parent=self)
        if nueva:
            from validacion import _reports_root
            import validacion
            validacion._reports_root = nueva
            self._refresh_reports_ui()
            self._log(f"Carpeta raiz de reportes cambiada: {nueva}", C_GREEN)
        else:
            self._log("Cambio de carpeta cancelado.", C_YELLOW)

    def _abrir_carpeta_raiz(self):
        import subprocess, platform
        root = get_current_reports_root()
        if not root:
            QMessageBox.information(self, "Sin carpeta", "Aun no se ha configurado la carpeta raiz.")
            return
        os.makedirs(root, exist_ok=True)
        try:
            if platform.system() == "Windows":   os.startfile(root)
            elif platform.system() == "Darwin":  subprocess.Popen(["open", root])
            else:                                subprocess.Popen(["xdg-open", root])
        except Exception as e:
            self._log(f"No se pudo abrir la carpeta: {e}", C_RED)

    def _limpiar_reportes(self):
        root = get_current_reports_root()
        if not root or not os.path.isdir(root):
            QMessageBox.information(self, "Sin carpeta", "No hay carpeta de reportes configurada.")
            return
        cat = self._combo_cat.currentText()
        if cat == "Todas las categorias":
            subcarpetas = [
                d for d in os.listdir(root)
                if os.path.isdir(os.path.join(root, d))
            ]
            total = sum(
                len([f for f in os.listdir(os.path.join(root, d)) if f.endswith(".pdf")])
                for d in subcarpetas
            )
            reply = QMessageBox.question(
                self, "Confirmar limpieza",
                f"Se eliminaran {total} PDF(s) de todas las categorias en:\n{root}\n\n"
                f"Las carpetas se recrearan vacias. Continuar?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            for d in subcarpetas:
                path = os.path.join(root, d)
                shutil.rmtree(path)
                os.makedirs(path, exist_ok=True)
            self._log(f"Todas las categorias limpiadas ({total} PDF(s) eliminados).", C_YELLOW)
        else:
            path  = os.path.join(root, cat)
            count = len([f for f in os.listdir(path) if f.endswith(".pdf")]) if os.path.isdir(path) else 0
            reply = QMessageBox.question(
                self, "Confirmar limpieza",
                f"Se eliminaran {count} PDF(s) de la categoria '{cat}' en:\n{path}\n\n"
                f"La carpeta se recreara vacia. Continuar?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            if os.path.isdir(path):
                shutil.rmtree(path)
            os.makedirs(path, exist_ok=True)
            self._log(f"Categoria '{cat}' limpiada ({count} PDF(s) eliminados).", C_YELLOW)

        self._refresh_reports_ui()

    def _build_log(self):
        box = QGroupBox("Registro de operaciones")
        box.setStyleSheet(
            f"QGroupBox {{ border:1px solid {C_OVERLAY}; border-radius:8px; margin-top:10px; "
            f"font-weight:bold; color:{C_BLUE}; padding:6px; }}"
            f"QGroupBox::title {{ subcontrol-origin:margin; left:10px; padding:0 6px; }}"
        )
        lay = QVBoxLayout(box)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(
            f"QTextEdit {{ background:{C_MANTLE}; color:{C_TEXT}; border:none; "
            f"border-radius:4px; font-family:Consolas,monospace; font-size:12px; }}"
        )
        lay.addWidget(self.log)
        return box

    def _build_action_bar(self):
        bar = QHBoxLayout()
        bar.addStretch()
        self.btn_borrar = QPushButton("Borrar hojas seleccionadas")
        self.btn_borrar.setFixedHeight(40)
        self.btn_borrar.setFixedWidth(260)
        self.btn_borrar.setStyleSheet(
            f"QPushButton {{ background:#7f1d1d; color:{C_RED}; border:1px solid #ef4444; "
            f"border-radius:6px; font-size:13px; font-weight:700; }}"
            f"QPushButton:hover {{ background:#991b1b; }}"
            f"QPushButton:disabled {{ background:#2a1010; color:#6b3030; border-color:#4a1818; }}"
        )
        self.btn_borrar.clicked.connect(self._confirmar_borrado)
        bar.addWidget(self.btn_borrar)
        w = QWidget(); w.setLayout(bar)
        return w

    def _confirmar_borrado(self):
        targets = [n for n, cb in self._checks.items() if cb.isChecked()]
        if not targets:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona al menos una hoja.")
            return
        lista = "\n  - ".join(targets)
        reply = QMessageBox.question(
            self, "Confirmar borrado",
            f"Borrar TODOS los datos de:\n\n  - {lista}\n\nEsta accion no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.btn_borrar.setEnabled(False)
        self._log(f"Iniciando borrado: {', '.join(targets)}", C_YELLOW)
        self._worker = ClearWorker(self.sheet_id, self.sheet_map, targets, self.header_row)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, msg, is_error):
        self._log(msg, C_RED if is_error else C_GREEN)

    def _on_finished(self):
        self._log("Operacion completada.", C_BLUE)
        self.btn_borrar.setEnabled(True)
        for cb in self._checks.values():
            cb.setChecked(False)

    def _log(self, msg, color=C_TEXT):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(
            f'<span style="color:{C_SUBTEXT}">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )

    def cleanup(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()


class TabAdmin(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, sheet_id, sheet_map, header_row=1):
        super().__init__()
        self._sheet_map    = sheet_map
        self._stack        = QStackedWidget()
        self._login_widget = LoginWidget()
        self._admin_panel  = AdminPanel(sheet_id, sheet_map, header_row)
        self._stack.addWidget(self._login_widget)
        self._stack.addWidget(self._admin_panel)
        self._login_widget.login_ok.connect(self._on_login)
        self._admin_panel.logout.connect(self._on_logout)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._stack)

    def _on_login(self, username):
        combo = self._admin_panel._combo_cat
        combo.clear()
        combo.addItem("Todas las categorias")
        for name in self._sheet_map.values():
            combo.addItem(name)
        self._admin_panel._combo_cat.currentIndexChanged.connect(
            self._admin_panel._update_count
        )
        self._admin_panel.set_user(username)
        self._admin_panel._refresh_reports_ui()
        self._stack.setCurrentIndex(1)
        self.status_msg.emit(f"Admin: sesion iniciada como '{username}'.")

    def _on_logout(self):
        self._login_widget.reset()
        self._stack.setCurrentIndex(0)
        self.status_msg.emit("Admin: sesion cerrada.")

    def cleanup(self):
        self._admin_panel.cleanup()
