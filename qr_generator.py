#Requisitos: pip install PyQt5 qrcode pillow


import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QGroupBox, QComboBox, QSpinBox, QLineEdit,
    QFileDialog, QMessageBox, QGridLayout, QFrame, QStatusBar,
    QScrollArea, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap, QIcon

try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    HAS_QR = True
except ImportError:
    HAS_QR = False


STYLE = """
* { font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QMainWindow, QWidget { background: #1e1e2e; color: #cdd6f4; }
QGroupBox {
    background: #242438; border: 1px solid #3b3b55; border-radius: 10px;
    margin-top: 14px; padding: 14px 12px 10px 12px;
    font-weight: 600; color: #89b4fa; font-size: 11px;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; background: #242438; }
QPushButton {
    background: #2a2a40; color: #cdd6f4; border: 1px solid #3b3b55;
    border-radius: 6px; padding: 7px 16px;
}
QPushButton:hover { background: #35354d; border-color: #89b4fa; }
QPushButton[primary="true"] {
    background: #2563eb; color: white; border: none; font-weight: 700;
}
QPushButton[primary="true"]:hover { background: #1d4ed8; }
QComboBox, QLineEdit, QSpinBox {
    background: #2a2a40; color: #cdd6f4; border: 1px solid #3b3b55;
    border-radius: 6px; padding: 6px 10px;
}
QComboBox:hover, QLineEdit:focus, QSpinBox:focus { border-color: #2563eb; }
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView { background: #242438; color: #cdd6f4; border: 1px solid #3b3b55; }
QLabel { color: #cdd6f4; }
QStatusBar { background: #181825; color: #7f849c; border-top: 1px solid #3b3b55; }
QScrollBar:vertical { background: #181825; width: 8px; }
QScrollBar::handle:vertical { background: #3b3b55; border-radius: 4px; }
"""


def _get_font(size: int):
    """Intenta cargar una fuente del sistema, fallback a default de Pillow."""
    candidates = [
        "arialbd.ttf", "Arial Bold.ttf",
        "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _make_sticker(qr_id: str, qr_size: int, footer_h: int) -> Image.Image:
    """
    Genera una imagen de sticker: QR arriba + footer con el ID abajo.
    Retorna imagen PIL RGB.
    """
    # QR en blanco y negro
    qr_img = qrcode.make(qr_id).resize(
        (qr_size, qr_size), Image.Resampling.LANCZOS
    ).convert("RGB")

    # Canvas total
    total_h = qr_size + footer_h
    sticker = Image.new("RGB", (qr_size, total_h), "white")
    sticker.paste(qr_img, (0, 0))

    # Footer con texto centrado
    draw = ImageDraw.Draw(sticker)
    font_size = max(10, footer_h - 6)
    font = _get_font(font_size)

    label = _short_label(qr_id)

    try:
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:

        tw, th = draw.textsize(label, font=font)

    x = (qr_size - tw) // 2
    y = qr_size + (footer_h - th) // 2


    draw.text((x + 1, y + 1), label, fill="#cccccc", font=font)
    draw.text((x, y),         label, fill="#000000", font=font)

    return sticker


def _short_label(qr_id: str) -> str:
    """
    Convierte  'ESP32-BALAM-001'  →  'ESP32-001'
               'ROBOFUT-BALAM-012' →  'ROBOFUT-012'
    Si el formato no coincide devuelve el string original.
    """
    parts = qr_id.split("-BALAM-")
    if len(parts) == 2:
        prefix = parts[0]

        abbrev = {
            "ROBOFUT":     "Robofut",
            "TODOTERRENO": "Todoterreno",
            "STEM_SR":     "STEM SR",
            "STEM_JR":     "STEM JR",
            "DRONES":      "Drones",
            "IOT":         "IOT",
            "ESP32":       "ESP32",
        }
        label_prefix = abbrev.get(prefix.upper(), prefix)
        return f"{label_prefix}-{parts[1]}"
    return qr_id


class QRPreviewWidget(QLabel):
    def __init__(self, qr_text, size=120, parent=None):
        super().__init__(parent)
        self.setFixedSize(size + 10, size + 46)   
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: white; border-radius: 6px; padding: 4px;")

        if HAS_QR:
            sticker = _make_sticker(qr_text, size, 26)
            sticker_rgb = sticker.convert("RGB")
            from PyQt5.QtGui import QImage
            data = sticker_rgb.tobytes("raw", "RGB")
            qimg = QImage(data, sticker_rgb.width, sticker_rgb.height,
                          sticker_rgb.width * 3, QImage.Format_RGB888)
            self.setPixmap(QPixmap.fromImage(qimg))


class QRGeneratorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tesla Lab — Generador de QR")
        self.setMinimumSize(700, 620)
        self.resize(820, 670)
        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)


        header = QHBoxLayout()
        title = QLabel("Generador de Stickers QR")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setStyleSheet("color: #fab387;")
        header.addWidget(title)
        header.addStretch()

        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "TEST_STATION", "imgs", "LOGO TESLA-13.png")
        if not os.path.exists(logo_path):
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "imgs", "LOGO TESLA-13.png")
        if os.path.exists(logo_path):
            logo = QLabel()
            logo.setPixmap(QPixmap(logo_path).scaledToHeight(36, Qt.SmoothTransformation))
            header.addWidget(logo)
        root.addLayout(header)


        box = QGroupBox("Configuración")
        grid = QGridLayout(box)

        grid.addWidget(QLabel("Tipo:"), 0, 0)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["ESP32", "Shield"])
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        grid.addWidget(self.type_combo, 0, 1)

        grid.addWidget(QLabel("Shield:"), 0, 2)
        self.shield_combo = QComboBox()
        self.shield_combo.addItems(["Robofut", "Todoterreno", "STEM SR", "STEM JR", "Drones", "IOT"])
        self.shield_combo.setEnabled(False)
        grid.addWidget(self.shield_combo, 0, 3)

        grid.addWidget(QLabel("Desde:"), 1, 0)
        self.from_spin = QSpinBox()
        self.from_spin.setRange(0, 9999)
        self.from_spin.setValue(1)
        grid.addWidget(self.from_spin, 1, 1)

        grid.addWidget(QLabel("Hasta:"), 1, 2)
        self.to_spin = QSpinBox()
        self.to_spin.setRange(0, 9999)
        self.to_spin.setValue(30)
        grid.addWidget(self.to_spin, 1, 3)

        grid.addWidget(QLabel("Tamaño QR (px):"), 2, 0)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(100, 500)
        self.size_spin.setValue(200)
        self.size_spin.setSingleStep(50)
        grid.addWidget(self.size_spin, 2, 1)

        grid.addWidget(QLabel("Columnas:"), 2, 2)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 10)
        self.cols_spin.setValue(8)
        grid.addWidget(self.cols_spin, 2, 3)

        grid.addWidget(QLabel("Alto footer (px):"), 3, 0)
        self.footer_spin = QSpinBox()
        self.footer_spin.setRange(16, 80)
        self.footer_spin.setValue(32)
        self.footer_spin.setSingleStep(4)
        self.footer_spin.setToolTip("Altura del área de texto bajo el QR")
        grid.addWidget(self.footer_spin, 3, 1)

        grid.addWidget(QLabel("Formato:"), 3, 2)
        self.format_label = QLabel("")
        self.format_label.setStyleSheet("color: #89b4fa; font-weight: 700; font-size: 13px;")
        grid.addWidget(self.format_label, 3, 3)

        root.addWidget(box)

        for widget in [self.type_combo, self.shield_combo]:
            widget.currentIndexChanged.connect(self._update_preview)
        for widget in [self.from_spin, self.to_spin]:
            widget.valueChanged.connect(self._update_preview)
        self._update_preview()

        preview_box = QGroupBox("Vista previa (primeros 6)")
        pl = QHBoxLayout(preview_box)
        self.preview_area = QHBoxLayout()
        self.preview_area.setSpacing(8)
        pl.addLayout(self.preview_area)
        pl.addStretch()
        root.addWidget(preview_box)

        btn_preview = QPushButton("Actualizar vista previa")
        btn_preview.clicked.connect(self._show_preview)
        root.addWidget(btn_preview)

        gen_row = QHBoxLayout()
        gen_row.addStretch()
        self.btn_gen = QPushButton("Generar PDF de Stickers")
        self.btn_gen.setProperty("primary", True)
        self.btn_gen.setFixedHeight(42)
        self.btn_gen.setFixedWidth(260)
        self.btn_gen.setCursor(Qt.PointingHandCursor)
        self.btn_gen.clicked.connect(self._generate)
        gen_row.addWidget(self.btn_gen)
        gen_row.addStretch()
        root.addLayout(gen_row)

        info = QLabel(
            "ℹ Máximo 30 stickers por página. Rangos mayores generan múltiples páginas.\n"
            "Cada sticker incluye el QR + etiqueta (ej: ESP32-001, Robofut-012)."
        )
        info.setStyleSheet("color: #7f849c; font-size: 11px;")
        info.setWordWrap(True)
        root.addWidget(info)

        root.addStretch()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo")

    def _on_type_changed(self, idx):
        self.shield_combo.setEnabled(idx == 1)
        self._update_preview()

    def _get_prefix(self):
        if self.type_combo.currentText() == "ESP32":
            return "ESP32"
        return self.shield_combo.currentText().upper().replace(" ", "_")

    def _update_preview(self):
        prefix = self._get_prefix()
        n_from = self.from_spin.value()
        n_to   = self.to_spin.value()
        count  = max(0, n_to - n_from + 1)
        self.format_label.setText(
            f"{prefix}-BALAM-{n_from:03d}  →  {prefix}-BALAM-{n_to:03d}    ({count} stickers)"
        )

    def _show_preview(self):
        while self.preview_area.count():
            item = self.preview_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        prefix = self._get_prefix()
        n_from = self.from_spin.value()
        n_to   = self.to_spin.value()

        for i in range(n_from, min(n_from + 6, n_to + 1)):
            qr_id = f"{prefix}-BALAM-{i:03d}"
            w = QRPreviewWidget(qr_id, 100)
            self.preview_area.addWidget(w)

    def _generate(self):
        if not HAS_QR:
            QMessageBox.warning(self, "Error",
                "Dependencias faltantes.\nInstalar:\n  pip install qrcode pillow")
            return

        prefix = self._get_prefix()
        n_from = self.from_spin.value()
        n_to   = self.to_spin.value()
        if n_to < n_from:
            QMessageBox.warning(self, "Error", "'Hasta' debe ser >= 'Desde'")
            return

        ids        = [f"{prefix}-BALAM-{i:03d}" for i in range(n_from, n_to + 1)]
        qr_size    = self.size_spin.value()
        footer_h   = self.footer_spin.value()
        cols       = self.cols_spin.value()
        margin     = 20
        page_margin = 50
        max_per_page = 30

        # Altura de cada celda = QR + footer
        cell_h = qr_size + footer_h

        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF",
            f"stickers_{prefix}_{n_from}-{n_to}.pdf",
            "PDF (*.pdf)"
        )
        if not save_path:
            return

        self.status_bar.showMessage("Generando...")
        QApplication.processEvents()

        pages = []
        for page_start in range(0, len(ids), max_per_page):
            page_ids = ids[page_start:page_start + max_per_page]
            rows = -(-len(page_ids) // cols)

            w = (qr_size  * cols) + (margin * (cols - 1)) + (page_margin * 2)
            h = (cell_h   * rows) + (margin * (rows - 1)) + (page_margin * 2)
            sheet = Image.new("RGB", (w, h), "white")

            for idx, qr_id in enumerate(page_ids):
                r, c = divmod(idx, cols)
                sticker = _make_sticker(qr_id, qr_size, footer_h)
                x = page_margin + c * (qr_size + margin)
                y = page_margin + r * (cell_h  + margin)
                sheet.paste(sticker, (x, y))

            pages.append(sheet)

        if pages:
            pages[0].save(save_path, save_all=True, append_images=pages[1:])
            self.status_bar.showMessage(
                f"{len(ids)} stickers en {len(pages)} página(s) → {save_path}"
            )
            QMessageBox.information(self, "Listo",
                f"PDF generado:\n{save_path}\n\n"
                f"{len(ids)} stickers en {len(pages)} página(s)")
        else:
            self.status_bar.showMessage("Error al generar.")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    logo_path2 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "..", "TEST_STATION", "imgs", "LOGO TESLA-09.png")
    if not os.path.exists(logo_path2):
        logo_path2 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "imgs", "LOGO TESLA-09.png")
    if os.path.exists(logo_path2):
        app.setWindowIcon(QIcon(logo_path2))

    window = QRGeneratorWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()