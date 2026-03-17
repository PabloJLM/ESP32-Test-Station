<h1 align="center">
Tesla Test Station
</h1>

<p align="center">
  Herramientas para generación de códigos QR y pruebas con ESP32
</p>

<p align="center">
  <a href="https://www.python.org">
    <img src="https://img.shields.io/badge/Python-3.10-3776AB.svg?style=flat&logo=python&logoColor=white">
  </a>
  <a href="https://www.arduino.cc/">
    <img src="https://img.shields.io/badge/Arduino-2.3.7-blue?style=flat&logo=Arduino">
  </a>
  <img src="https://img.shields.io/badge/ESP32-Espressif-red?style=flat&logo=espressif&logoColor=white">
  <img src="https://img.shields.io/badge/Google%20Sheets-34A853?style=flat&logo=google-sheets&logoColor=white">
</p>

Repositorio que contiene dos aplicaciones:
- Generador de códigos QR
- Test Station (en desarrollo)
---

## Estado del proyecto
![](https://img.shields.io/badge/-En%20desarrollo-yellow?style=for-the-badge&logo=github)
---

## Aplicaciones

### 1. QR Generator
Genera codigos QR especificamente para proyecto BALAM 2026


### 2. Test Station
Es la estacion de pruebas xd

---

## Como generar archivos .exe
Se pueden crear archivos .exe con la siguiente aplicacion de python [auto-py-to-exe](https://pypi.org/project/auto-py-to-exe/)
Contiene una interfaz simple en donde se puede parametrizar la salida del archivo 
### Instalacion
Usa este comando para instalarlo
``` bash
pip install auto-py-to-exe
```
Una vez instalado puedes activar la interfaz con el siguiente comando:

``` bash
auto-py-to-exe
```
Una vez iniciado la interfaz se deben seguir estos pasos

 1. Se debe elegir el archivo .py a convertir 
 2. Se selecciona en modo **One File** para computadoras sin Python env 
 3. Si el archivo esta programado como una GUI se debe elegir en modo **Window based** de lo contrario se puede poner en modo **Console Based**

<figure>
  <img src="imgs/Config_exe.png" alt="Configuracion de ejemplo">
  <figcaption>Figura 1: Configuracion basica</figcaption>
</figure>

 4. Se añade el icono *(opcional)* 
 5. Se pueden añadir archivos o carpetas adicionales, segun sean necesarios para el programa

> Nota: se deben añadir todos los archivos secundarios que usa el
> programa

<figure>
  <img src="imgs/icon_config.png" alt="Icon & additional files">
  <figcaption>Figura 2: Configuracion de icono y archivos adicionales</figcaption>
</figure>

Finalmente el archivo .exe estara en la carpeta **output**
>Al ser un archivo **standalone** puede pesar varias megas y en la carpeta output solamente debe haber un archivo (si se eligio en modo One File)
