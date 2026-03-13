import gspread
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

# Configuración
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def generar_token():
    """Genera un nuevo archivo token.json"""
    creds = None
    
    # Verificar si ya existe token (en tu caso no existe)
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si no hay credenciales válidas, iniciar flujo
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("Abriendo navegador para autenticación...")
            print("Por favor, autoriza la aplicación con tu cuenta personal")
            
            # Esto abrirá el navegador
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', 
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # ¡ESTA ES LA PARTE IMPORTANTE!
        # Guarda el token como token.json
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
        
        print("¡Nuevo token.json generado correctamente!")
        print("Archivo guardado en:", os.path.abspath('token.json'))
    
    return creds

# Ejecutar
if __name__ == "__main__":
    if not os.path.exists('credentials.json'):
        print("Primero necesitas el archivo credentials.json")
        print("Descárgalo desde Google Cloud Console > Credenciales > tu cliente OAuth > botón DESCARGAR JSON")
    else:
        creds = generar_token()
        print("\nTodo listo! Ya puedes usar tu token.json")