import gspread
# Conectar a la hoja de cálculo usando OAuth
gc = gspread.oauth(
    credentials_filename='credentials.json',
    authorized_user_filename='token.json'
)
# Abrir la hoja de cálculo usando su ID
sheet = gc.open_by_key('13WIYurPQvRztU1xpUru8-COzgfdPzqvTP4hEZM6pX2I')

#diccionario de worksheets ESP32, Robofut, Todoterreno, STEM SR, STEM JR, Drones, IOT
worksheet_names = {
    "ESP32" : sheet.get_worksheet(0),
    "Robofut" : sheet.get_worksheet(1),
    "Todoterreno" : sheet.get_worksheet(2),
    "STEM SR" : sheet.get_worksheet(3),
    "STEM JR" : sheet.get_worksheet(4),
    "Drones" : sheet.get_worksheet(5),
    "IOT" : sheet.get_worksheet(6),
}

#funciones 
#1. ver hoja especifica if celda == 'A1'or 'A1' or 'A1' or 'A1':
def get_worksheet(name):
    return worksheet_names[name]

#2. leer valores de celdas especificos 
def get_value(ws, celda): #usar notacion A1 
    ws = worksheet_names[ws]
    value = ws.acell(celda).value
    return value
#3. set valores menos en las predeterminadas
def set_value(ws, celda, contenido):
    ws = worksheet_names[ws]
    if celda == 'A1' or celda == 'B1' or celda == 'C1' or celda == 'D1':
        print("No se puede modificar esta celda!")
        
    else:
        ws.update_acell(celda,contenido)
        print("Se modifico: " + celda + " con: " + contenido)

def borrar_celda(ws,celda):
    ws=worksheet_names[ws]
    ws.update_acell(celda,'')
    print("Se borro la celda: " + celda)    

#set_value('Drones','A4','AAAAA')
#borrar_celda('Drones','A4')