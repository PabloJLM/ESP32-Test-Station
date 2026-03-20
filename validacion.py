import os
import shutil
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QComboBox,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QImage


# ══════════════════════════════════════════════════════════════
#  HILO CÁMARA
# ══════════════════════════════════════════════════════════════
class CameraThread(QThread):
    frame_ready = pyqtSignal(QImage)
    qr_detected = pyqtSignal(str)

    def __init__(self, cam_id=0):
        super().__init__()
        self.cam_id    = cam_id
        self._running  = False
        self._last_qr  = None
        self._cooldown = 0

    def run(self):
        self._running = True
        try:
            import cv2
        except ImportError:
            return
        cap = cv2.VideoCapture(self.cam_id)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        qcd = cv2.QRCodeDetector()
        while self._running:
            ret, frame = cap.read()
            if not ret:
                self.msleep(50)
                continue
            if self._cooldown > 0:
                self._cooldown -= 1
            else:
                ok, decoded, points, _ = qcd.detectAndDecodeMulti(frame)
                if ok:
                    for s, p in zip(decoded, points):
                        if s and s != self._last_qr:
                            self._last_qr  = s
                            self._cooldown = 30
                            cv2.polylines(frame, [p.astype(int)], True, (0, 255, 0), 3)
                            self.qr_detected.emit(s)
            rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            self.frame_ready.emit(
                QImage(rgb.data, w, h, w * ch, QImage.Format_RGB888).copy()
            )
            self.msleep(30)
        cap.release()

    def stop(self):
        self._running = False
        self._last_qr = None
        self.wait()


# ══════════════════════════════════════════════════════════════
#  HILO GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════
class SheetsWorker(QThread):
    done = pyqtSignal(bool, str)

    def __init__(self, sheet_id, sheet_name, qr_code, estado,
                 col_config, header_row, qr_pattern, notas=""):
        super().__init__()
        self.sheet_id   = sheet_id
        self.sheet_name = sheet_name
        self.qr_code    = qr_code
        self.estado     = estado
        self.notas      = notas
        self.header_row = header_row
        self.qr_pattern = qr_pattern
        self.col_estado, self.col_id, self.col_qr, self.col_ts, self.col_notas = col_config

    def run(self):
        try:
            import gspread
            gc = gspread.oauth(
                credentials_filename='credentials.json',
                authorized_user_filename='token.json'
            )
            ws = gc.open_by_key(self.sheet_id).worksheet(self.sheet_name)

            m      = self.qr_pattern.match(self.qr_code)
            id_num = m.group(2) if m else self.qr_code
            ts     = datetime.now().strftime("%d/%m/%Y %H:%M")

            col_c      = ws.col_values(3)
            target_row = next(
                (i + 1 for i, v in enumerate(col_c)
                 if str(v).strip().upper() == self.qr_code.upper()),
                max(len(col_c) + 1, self.header_row + 1)
            )

            ws.update_acell(f'{self.col_estado}{target_row}', self.estado)
            ws.update_acell(f'{self.col_id}{target_row}',     id_num)
            ws.update_acell(f'{self.col_qr}{target_row}',     self.qr_code)
            ws.update_acell(f'{self.col_ts}{target_row}',     ts)
            if self.notas:
                ws.update_acell(f'{self.col_notas}{target_row}', self.notas)

            r, g = (0.0, 1.0) if self.estado == "OK" else (1.0, 0.0)
            ws.format(f'{self.col_estado}{target_row}', {
                "backgroundColor": {"red": r, "green": g, "blue": 0.0}
            })
            self.done.emit(True, f"Fila {target_row} en '{self.sheet_name}'")

        except FileNotFoundError:
            self.done.emit(False, "credentials.json / token.json no encontrado")
        except Exception as e:
            self.done.emit(False, str(e))


# ══════════════════════════════════════════════════════════════
#  GENERADOR DE REPORTE PDF
# ══════════════════════════════════════════════════════════════
def generar_reporte_pdf(data: dict, qr_pattern, logo_path: str = None) -> str:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table,
        TableStyle, HRFlowable, Image as RLImage
    )

    def sty(name, parent='Normal', **kw):
        return ParagraphStyle(name, parent=getSampleStyleSheet()[parent], **kw)

    ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname   = f"reporte_{data['qr_code'].replace('/', '-')}_{ts_file}.pdf"
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    fpath   = os.path.join(desktop if os.path.isdir(desktop) else os.getcwd(), fname)

    doc = SimpleDocTemplate(
        fpath, pagesize=letter,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=2*cm,
        title=f"Reporte Tesla Lab — {data['qr_code']}"
    )

    title_s = sty('TT', fontSize=20, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#1e3a5f'), spaceAfter=2)
    sub_s   = sty('TS', fontSize=10, fontName='Helvetica',
                  textColor=colors.HexColor('#555555'), spaceAfter=0)
    sec_s   = sty('TC', fontSize=12, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#1e3a5f'), spaceBefore=12, spaceAfter=6)
    body_s  = sty('TB', fontSize=10, fontName='Helvetica',
                  textColor=colors.HexColor('#333333'), leading=14)
    lbl_s   = sty('LB', fontSize=9, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#666666'))

    story = []

    # Encabezado
    logo_cell = (
        RLImage(logo_path, width=5*cm, height=1.6*cm, kind='proportional')
        if logo_path and os.path.exists(logo_path)
        else Paragraph("<b>TESLA LAB</b>", title_s)
    )
    hdr = Table([[logo_cell, [Paragraph("REPORTE DE VALIDACIÓN", title_s)]]], colWidths=[5.5*cm, None])
    hdr.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',         (1,0), (1,0),   'RIGHT'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=2,
                            color=colors.HexColor('#1e3a5f'), spaceAfter=10))

    # Badge estado
    is_ok   = data['estado'].upper() == "OK"
    badge_s = sty('BD', fontSize=16, fontName='Helvetica-Bold',
                  textColor=colors.HexColor('#155724' if is_ok else '#721c24'), alignment=1)
    badge_t = Table(
        [[Paragraph("✔  VALIDACIÓN EXITOSA" if is_ok else "✘  VALIDACIÓN FALLIDA", badge_s)]],
        colWidths=['100%']
    )
    badge_t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor('#d4edda' if is_ok else '#f8d7da')),
        ('BOX',           (0,0), (-1,-1), 1.5, colors.HexColor('#28a745' if is_ok else '#dc3545')),
        ('TOPPADDING',    (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(badge_t)
    story.append(Spacer(1, 14))

    # Tabla de datos
    story.append(Paragraph("Información del Dispositivo", sec_s))
    m = qr_pattern.match(data['qr_code'])
    dev_t = Table([
        [Paragraph("Campo", lbl_s),  Paragraph("Valor", lbl_s)],
        ["Código QR",    data['qr_code']],
        ["Tipo",         m.group(1).upper() if m else "—"],
        ["ID / Número",  m.group(2)         if m else "—"],
        ["Hoja (Sheet)", data.get('sheet',    '—')],
        ["Estado",       data['estado']],
        ["Timestamp",    data['timestamp']],
        ["Encargado",    data.get('encargado', 'No especificado')],
    ], colWidths=[5*cm, None])
    dev_t.setStyle(TableStyle([
        ('BACKGROUND',     (0,0), (-1,0),  colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR',      (0,0), (-1,0),  colors.white),
        ('FONTNAME',       (0,0), (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#f5f5f5'), colors.white]),
        ('BOX',            (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('GRID',           (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
        ('LEFTPADDING',    (0,0), (-1,-1), 8),
        ('TOPPADDING',     (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',  (0,0), (-1,-1), 6),
        ('FONTNAME',       (0,1), (0,-1),  'Helvetica-Bold'),
        ('TEXTCOLOR',      (0,1), (0,-1),  colors.HexColor('#333333')),
    ]))
    story.append(dev_t)

    # Notas
    story.append(Paragraph("Notas / Observaciones", sec_s))
    notas = data.get('notas', '').strip()
    story.append(Paragraph(
        notas if notas else '<font color="#999999"><i>Sin notas adicionales.</i></font>',
        body_s
    ))

    # Pie
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5,
                            color=colors.HexColor('#cccccc'), spaceAfter=5))
    story.append(Paragraph(
        f'<font size="8" color="#888888">Tesla Lab · Universidad Galileo · '
        f'Reporte generado automáticamente · {data["timestamp"]}</font>', body_s
    ))

    doc.build(story)
    return fpath


# ══════════════════════════════════════════════════════════════
#  PESTAÑA VALIDACIÓN
# ══════════════════════════════════════════════════════════════
class TabValidacion(QWidget):
    status_msg = pyqtSignal(str)

    def __init__(self, logo_path=None, sheet_id=None, sheet_map=None,
                 qr_pattern=None, col_config=None, header_row=1):
        super().__init__()
        self.logo_path   = logo_path
        self.sheet_id    = sheet_id
        self.sheet_map   = sheet_map or {}
        self.qr_pattern  = qr_pattern
        self.col_config  = col_config
        self.header_row  = header_row
        self.cam_thread  = None
        self.last_qr     = None
        self.encargado   = ""
        self._sheets_worker = None
        self._build_ui()

    # ── API pública ──────────────────────────────────────────────
    def set_encargado(self, nombre: str):
        """
        Recibe el username del login general y lo aplica
        al campo encargado. El campo queda editable por si
        se quiere cambiar manualmente.
        """
        self.encargado = nombre
        self.op_input.setText(nombre)

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(10, 10, 10, 10)
        root.addLayout(self._build_camera_col(), 3)
        root.addLayout(self._build_controls_col(), 2)

    def _build_camera_col(self):
        col = QVBoxLayout()
        box = QGroupBox("Cámara / Lector QR")
        lay = QVBoxLayout(box)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Cámara:"))
        self.cam_combo = QComboBox()
        self.cam_combo.addItems(["0", "1", "2", "3"])
        ctrl.addWidget(self.cam_combo)
        self.btn_cam = QPushButton("Iniciar cámara")
        self.btn_cam.setProperty("primary", True)
        self.btn_cam.clicked.connect(self._toggle_camera)
        ctrl.addWidget(self.btn_cam)
        lay.addLayout(ctrl)

        self.cam_label = QLabel("[ Sin señal de cámara ]")
        self.cam_label.setFixedSize(560, 420)
        self.cam_label.setAlignment(Qt.AlignCenter)
        self.cam_label.setStyleSheet(
            "background:#0d0d1a; border:1px solid #45475a; "
            "border-radius:8px; color:#585b70;"
        )
        lay.addWidget(self.cam_label)

        manual = QHBoxLayout()
        manual.addWidget(QLabel("QR manual:"))
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("ESP32-BALAM-001")
        self.manual_input.returnPressed.connect(self._on_manual_qr)
        manual.addWidget(self.manual_input)
        btn_m = QPushButton("Validar")
        btn_m.clicked.connect(self._on_manual_qr)
        manual.addWidget(btn_m)
        lay.addLayout(manual)

        col.addWidget(box)
        return col

    def _build_controls_col(self):
        col = QVBoxLayout()
        col.setSpacing(8)

        # Sesión / Encargado
        box_op = QGroupBox("Sesión")
        lay_op = QHBoxLayout(box_op)
        lay_op.addWidget(QLabel("Encargado:"))
        self.op_input = QLineEdit(self.encargado)
        self.op_input.setPlaceholderText("Nombre del encargado")
        self.op_input.setReadOnly(True)   # solo lectura — se hereda del login
        self.op_input.setStyleSheet(
            "QLineEdit { background: #181825; color: #a6e3a1; "
            "border: 1px solid #45475a; border-radius: 4px; padding: 4px 8px; "
            "font-weight: 600; }"
        )
        self.op_input.textChanged.connect(lambda t: setattr(self, 'encargado', t))
        lay_op.addWidget(self.op_input)
        col.addWidget(box_op)

        # Dispositivo escaneado
        box_qr = QGroupBox("Dispositivo Escaneado")
        lay_qr = QVBoxLayout(box_qr)
        self.lbl_qr_code = QLabel("—")
        self.lbl_qr_code.setFont(QFont("Consolas", 15, QFont.Bold))
        self.lbl_qr_code.setStyleSheet("color:#cba6f7; letter-spacing:1px;")
        lay_qr.addWidget(self.lbl_qr_code)
        self.lbl_qr_info = QLabel("Tipo: —   |   ID: —   |   Hoja: —")
        self.lbl_qr_info.setStyleSheet("color:#a6e3a1; font-size:11px;")
        lay_qr.addWidget(self.lbl_qr_info)
        self.lbl_badge = QLabel("SIN ESCANEAR")
        self.lbl_badge.setAlignment(Qt.AlignCenter)
        self.lbl_badge.setFixedHeight(40)
        self.lbl_badge.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._set_badge("PENDING")
        lay_qr.addWidget(self.lbl_badge)
        col.addWidget(box_qr)

        # Acciones
        box_act = QGroupBox("Acciones")
        lay_act = QVBoxLayout(box_act)
        row = QHBoxLayout()
        self.btn_ok   = QPushButton("Marcar OK")
        self.btn_fail = QPushButton("Marcar FAIL")
        self.btn_ok.setProperty("success", True)
        self.btn_fail.setProperty("danger",  True)
        self.btn_ok.setFixedHeight(44)
        self.btn_fail.setFixedHeight(44)
        self.btn_ok.setEnabled(False)
        self.btn_fail.setEnabled(False)
        self.btn_ok.clicked.connect(lambda:   self._registrar("OK"))
        self.btn_fail.clicked.connect(lambda: self._registrar("FAIL"))
        row.addWidget(self.btn_ok)
        row.addWidget(self.btn_fail)
        lay_act.addLayout(row)
        self.btn_report = QPushButton("Generar Reporte PDF")
        self.btn_report.setFixedHeight(36)
        self.btn_report.setEnabled(False)
        self.btn_report.clicked.connect(self._generar_reporte)
        lay_act.addWidget(self.btn_report)
        btn_nuevo = QPushButton("↺  Nuevo escaneo")
        btn_nuevo.setFixedHeight(32)
        btn_nuevo.clicked.connect(self._limpiar)
        lay_act.addWidget(btn_nuevo)
        col.addWidget(box_act)

        # Último registro
        box_rec = QGroupBox("Último registro → Google Sheets")
        lay_rec = QGridLayout(box_rec)
        lay_rec.setColumnStretch(1, 1)
        self._rec = {}
        for i, lbl in enumerate(["Estado:", "ID:", "Codigo QR:", "Timestamp:", "Hoja:"]):
            lay_rec.addWidget(QLabel(lbl), i, 0)
            v = QLabel("—")
            v.setStyleSheet("color:#89b4fa;")
            lay_rec.addWidget(v, i, 1)
            self._rec[lbl] = v
        col.addWidget(box_rec)

        # Log
        box_log = QGroupBox("Log")
        lay_log = QVBoxLayout(box_log)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFixedHeight(120)
        lay_log.addWidget(self.log_text)
        btn_cl = QPushButton("Limpiar log")
        btn_cl.setFixedWidth(100)
        btn_cl.clicked.connect(self.log_text.clear)
        lay_log.addWidget(btn_cl)
        col.addWidget(box_log)

        col.addStretch()
        return col

    # ── Cámara ──────────────────────────────────────────────────
    def _toggle_camera(self):
        if self.cam_thread and self.cam_thread.isRunning():
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        cam_id = int(self.cam_combo.currentText().split()[0])
        self.cam_thread = CameraThread(cam_id)
        self.cam_thread.frame_ready.connect(self._update_frame)
        self.cam_thread.qr_detected.connect(self._process_qr)
        self.cam_thread.start()
        self.btn_cam.setText("Detener cámara")
        self._log("Cámara iniciada.")
        self.status_msg.emit("Cámara activa — apunta al QR.")

    def _stop_camera(self):
        if self.cam_thread:
            self.cam_thread.stop()
            self.cam_thread = None
        self.cam_label.setText("[ Sin señal de cámara ]")
        self.btn_cam.setText("Iniciar cámara")
        self._log("Cámara detenida.")

    def _update_frame(self, qimg):
        self.cam_label.setPixmap(
            QPixmap.fromImage(qimg).scaled(
                self.cam_label.width(), self.cam_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    # ── QR ──────────────────────────────────────────────────────
    def _on_manual_qr(self):
        qr = self.manual_input.text().strip()
        if qr:
            self._process_qr(qr)

    def _process_qr(self, qr_code: str):
        m = self.qr_pattern.match(qr_code)
        if not m:
            self._log(f"QR inválido: '{qr_code}'  — formato: TIPO-BALAM-NNN", "#f38ba8")
            self.status_msg.emit(f"QR inválido: {qr_code}")
            return
        tipo       = m.group(1).upper()
        id_num     = m.group(2)
        sheet_name = self.sheet_map.get(tipo, tipo)
        self.last_qr = {
            'qr_code':   qr_code,
            'tipo':      tipo,
            'id_num':    id_num,
            'sheet':     sheet_name,
            'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M"),
            'notas':     "",
            'estado':    None,
        }
        self.lbl_qr_code.setText(qr_code)
        self.lbl_qr_info.setText(f"Tipo: {tipo}   |   ID: {id_num}   |   Hoja: {sheet_name}")
        self._set_badge("PENDING")
        self.btn_ok.setEnabled(True)
        self.btn_fail.setEnabled(True)
        self.btn_report.setEnabled(False)
        self._log(f"QR leído: {qr_code}  →  hoja '{sheet_name}'", "#a6e3a1")
        self.status_msg.emit(f"QR listo: {qr_code}")

    # ── Registro ────────────────────────────────────────────────
    def _registrar(self, estado: str):
        if not self.last_qr:
            return
        notas, ok = QInputDialog.getText(
            self, "Notas opcionales",
            f"Notas para {self.last_qr['qr_code']}  (dejar vacío para omitir):",
            QLineEdit.Normal, ""
        )
        if not ok:
            return
        self.last_qr.update({
            'estado':    estado,
            'notas':     notas.strip(),
            'timestamp': datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        self._set_badge(estado)
        self.btn_ok.setEnabled(False)
        self.btn_fail.setEnabled(False)
        self.btn_report.setEnabled(True)

        color = "#a6e3a1" if estado == "OK" else "#f38ba8"
        self._rec["Estado:"].setText(estado)
        self._rec["Estado:"].setStyleSheet(f"color:{color};")
        self._rec["ID:"].setText(self.last_qr['id_num'])
        self._rec["Codigo QR:"].setText(self.last_qr['qr_code'])
        self._rec["Timestamp:"].setText(self.last_qr['timestamp'])
        self._rec["Hoja:"].setText(self.last_qr['sheet'])

        self._log(f"Enviando → {self.last_qr['qr_code']}  [{estado}]", "#89b4fa")
        self.status_msg.emit("Enviando a Google Sheets...")

        self._sheets_worker = SheetsWorker(
            sheet_id=self.sheet_id,
            sheet_name=self.last_qr['sheet'],
            qr_code=self.last_qr['qr_code'],
            estado=estado,
            col_config=self.col_config,
            header_row=self.header_row,
            qr_pattern=self.qr_pattern,
            notas=self.last_qr['notas'],
        )
        self._sheets_worker.done.connect(self._on_sheets_done)
        self._sheets_worker.start()

        if estado == "FAIL":
            if QMessageBox.question(
                self, "Generar reporte PDF",
                f"Dispositivo {self.last_qr['qr_code']} marcado FAIL.\n¿Generar reporte PDF ahora?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self._generar_reporte()

    def _on_sheets_done(self, success: bool, msg: str):
        color = "#a6e3a1" if success else "#f38ba8"
        self._log(f"{'Sheets OK' if success else 'Sheets ERROR'} → {msg}", color)
        self.status_msg.emit(f"{'Registrado' if success else 'Error'}: {msg}")

    # ── Reporte PDF ─────────────────────────────────────────────
    def _generar_reporte(self):
        if not self.last_qr or self.last_qr.get('estado') is None:
            QMessageBox.warning(self, "Sin datos", "Primero valida un dispositivo.")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte PDF",
            f"reporte_{self.last_qr['qr_code'].replace('/', '-')}.pdf",
            "PDF (*.pdf)"
        )
        if not save_path:
            return
        try:
            tmp = generar_reporte_pdf(
                {**self.last_qr, 'encargado': self.encargado},
                qr_pattern=self.qr_pattern,
                logo_path=self.logo_path
            )
            shutil.move(tmp, save_path)
            self._log(f"PDF guardado: {save_path}", "#a6e3a1")
            QMessageBox.information(self, "Reporte generado", f"Guardado en:\n{save_path}")
        except Exception as e:
            self._log(f"Error PDF: {e}", "#f38ba8")
            QMessageBox.critical(self, "Error", f"No se pudo generar el reporte:\n{e}")

    # ── Helpers ─────────────────────────────────────────────────
    def _set_badge(self, estado: str):
        cfg = {
            "OK":      ("✔  OK",      "background:#14532d; color:#86efac; border-radius:8px;"),
            "FAIL":    ("✘  FAIL",    "background:#7f1d1d; color:#fca5a5; border-radius:8px;"),
            "PENDING": ("PENDIENTE",  "background:#3b3b55; color:#cdd6f4; border-radius:8px;"),
        }
        txt, style = cfg.get(estado, cfg["PENDING"])
        self.lbl_badge.setText(txt)
        self.lbl_badge.setStyleSheet(style)

    def _limpiar(self):
        self.last_qr = None
        self.lbl_qr_code.setText("—")
        self.lbl_qr_info.setText("Tipo: —   |   ID: —   |   Hoja: —")
        self._set_badge("PENDING")
        self.btn_ok.setEnabled(False)
        self.btn_fail.setEnabled(False)
        self.btn_report.setEnabled(False)
        self.manual_input.clear()
        self._log("Listo para nuevo escaneo.")
        self.status_msg.emit("Listo.")

    def _log(self, msg: str, color: str = "#cdd6f4"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(
            f'<span style="color:#585b70">[{ts}]</span> '
            f'<span style="color:{color}">{msg}</span>'
        )

    def cleanup(self):
        self._stop_camera()
