import qrcode as qr
img = qr.make("Hola-12345-64789")
img.save("hola.png")