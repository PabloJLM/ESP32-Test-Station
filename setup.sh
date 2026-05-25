#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Tesla Lab BALAM 2026 — Setup Ubuntu
#  Correr UNA sola vez desde la carpeta del repo
# ═══════════════════════════════════════════════════════════
set -e
cd "$(dirname "$0")"

echo "=== [1/4] Dependencias del sistema ==="
sudo apt-get update -qq
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    libxcb-xinerama0 libxcb-cursor0 \
    libgl1-mesa-glx libglib2.0-0 \
    vlc v4l-utils

echo "=== [2/4] Permisos serial ==="
sudo usermod -aG dialout "$USER"

echo "=== [3/4] Entorno virtual ==="
python3 -m venv venv
source venv/bin/activate

echo "=== [4/4] Paquetes Python ==="
pip install --upgrade pip -q
pip install \
    PyQt5 pyserial \
    gspread google-auth-oauthlib google-auth google-api-python-client \
    reportlab "opencv-python-headless>=4.8" "qrcode[pil]" Pillow \
    esptool python-vlc

# Crear lanzador
RUTA="$(pwd)"
cat > run.sh << EOF
#!/bin/bash
cd "$RUTA"
source venv/bin/activate
export QT_QPA_PLATFORM=xcb
python3 esp32_tester.py "\$@"
EOF
chmod +x run.sh

# Crear .desktop
cat > ~/.local/share/applications/TeslaLab.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Tesla Lab BALAM 2026
Comment=ESP32 Test Station
Exec=bash $RUTA/run.sh
Icon=$RUTA/imgs/LOGO TESLA-13.png
Terminal=false
Categories=Science;
StartupWMClass=esp32_tester
EOF

echo ""
echo "=== Listo ==="
echo "IMPORTANTE: Cierra sesion y vuelve a entrar (permisos serial)"
echo "Luego puedes correr con:  ./run.sh"
echo "O busca 'Tesla Lab' en el menu de aplicaciones"