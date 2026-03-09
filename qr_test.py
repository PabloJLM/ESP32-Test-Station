import qrcode
from PIL import Image
import os

lista_ids = [f"ESP32-{i:03d}-BALAM" for i in range(1, 31)]


qr_individual_size = 200

# 5 filas x 6 columnas = 30 stickers
columnas = 6
filas = 5

margen_entre_qrs = 20    # Espacio entre sticker y sticker
margen_pagina = 50       # Espacio en los bordes de la hoja


nombre_archivo = "stickers.pdf"

def generar_hoja_stickers():
    """Genera un PDF con 30 códigos QR en cuadrícula"""
    
    print("Generando hoja de stickers...")
    
    # Calcular dimensiones de la hoja
    ancho_hoja = (qr_individual_size * columnas) + (margen_entre_qrs * (columnas - 1)) + (margen_pagina * 2)
    alto_hoja = (qr_individual_size * filas) + (margen_entre_qrs * (filas - 1)) + (margen_pagina * 2)
    
    # Crear lienzo en blanco
    hoja_stickers = Image.new('RGB', (ancho_hoja, alto_hoja), color='white')
    
    # Generar y colocar cada código QR
    indice = 0
    for fila in range(filas):
        for col in range(columnas):
            if indice < len(lista_ids):
                id_actual = lista_ids[indice]
                
                # Generar código QR
                img_qr = qrcode.make(id_actual)
                
                # Redimensionar al tamaño deseado
                img_qr = img_qr.resize((qr_individual_size, qr_individual_size), Image.Resampling.LANCZOS)
                
                # Calcular posición
                pos_x = margen_pagina + col * (qr_individual_size + margen_entre_qrs)
                pos_y = margen_pagina + fila * (qr_individual_size + margen_entre_qrs)
                
                # Pegar en la hoja
                hoja_stickers.paste(img_qr, (pos_x, pos_y))
                
                indice += 1
                print(f"  Generado {indice}/30: {id_actual}")
    
    # Guardar como PDF
    hoja_stickers.save(nombre_archivo)
    print(f"\n¡Listo! Archivo guardado como: {nombre_archivo}")
    print(f"   Ubicación: {os.path.abspath(nombre_archivo)}")

if __name__ == "__main__":
    generar_hoja_stickers()