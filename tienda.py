import os
import json
from bson.objectid import ObjectId
from flask import Blueprint, render_template, request, redirect, make_response
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from io import BytesIO
from reportlab.pdfgen import canvas
from num2words import num2words
from reportlab.lib import colors

def monto_a_letras(cantidad):
    entero = int(cantidad)
    centavos = int(round((cantidad - entero) * 100))
    letras = num2words(entero, lang='es').upper()
    if centavos > 0:
        letras_centavos = num2words(centavos, lang='es').upper()
        return f"({letras} PESOS CON {letras_centavos} CENTAVOS MXN)"
    return f"({letras} PESOS MEXICANOS)"

tienda_bp = Blueprint('tienda', __name__, template_folder='plantillas')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

MONGO_URI = "mongodb+srv://flopezvillarreal1_db_user:palabra2010@dmsa.cqsibku.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(MONGO_URI)
db = client["db_tienda"]

@tienda_bp.route('/')
def menu_principal():
    return render_template('menu.html')

@tienda_bp.route('/clientes', methods=['GET', 'POST'])
def gestionar_clientes():
    if request.method == 'POST':
        nombre = request.form.get('nombre_cliente') or ""
        ap = request.form.get('ap_cliente') or ""
        am = request.form.get('am_cliente') or ""
        tel = request.form.get('telefono') or ""
        
        foto = request.files.get('foto_c')
        ruta_foto = ""
        
        if foto and allowed_file(foto.filename):
            filename = secure_filename(foto.filename)
            ruta_guardado = os.path.join(UPLOAD_FOLDER, filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            foto.save(ruta_guardado)
            ruta_foto = ruta_guardado

        db.clientes.insert_one({
            "nombre_cliente": nombre,
            "ap_cliente": ap,
            "am_cliente": am,
            "telefono": tel,
            "fotos_c": ruta_foto
        })
        return redirect('/')

    return render_template('clientes.html')

@tienda_bp.route('/productos', methods=['GET', 'POST'])
def gestionar_productos():
    if request.method == 'POST':
        nombre = request.form.get('nombre_producto')
        marca = request.form.get('marca') or ""
        precio = float(request.form.get('precio') or 0)
        cantidad = int(request.form.get('cantidad') or 0)

        db.productos.insert_one({
            "nombre_producto": nombre,
            "marca": marca,
            "cantidad": cantidad,
            "precio": precio
        })
        return redirect('/')

    return render_template('productos.html')

@tienda_bp.route('/cajeros', methods=['GET', 'POST'])
def gestionar_cajeros():
    if request.method == 'POST':
        nombre = request.form.get('nombre_cajero')
        turno = request.form.get('turno') or ""
        cargo = request.form.get('cargo') or ""
        sueldo = float(request.form.get('sueldo') or 0)

        db.cajeros.insert_one({
            "nombre_cajero": nombre,
            "turno": turno,
            "cargo": cargo,
            "sueldo": sueldo
        })
        return redirect('/')

    return render_template('cajeros.html')

@tienda_bp.route('/nota_venta', methods=['GET', 'POST'])
def gestionar_ventas():
    if request.method == 'POST':
        id_cli = request.form.get('id_cliente')
        id_caj = request.form.get('id_cajero')
        fecha = request.form.get('fecha_vta')
        billete = float(request.form.get('billete_pago') or 0)
        carrito_raw = request.form.get('carrito_json', '[]')
        carrito = json.loads(carrito_raw)

        cli_data = db.clientes.find_one({"_id": ObjectId(id_cli)}) if ObjectId.is_valid(id_cli) else None
        if cli_data:
            nom = cli_data.get('nombre_cliente', '')
            nombre_cliente = f"{nom} {cli_data['ap_cliente']} {cli_data['am_cliente']}".strip()
        else:
            nombre_cliente = "Público en General"
        
        caj_data = db.cajeros.find_one({"_id": ObjectId(id_caj)}) if ObjectId.is_valid(id_caj) else None
        nombre_cajero = caj_data['nombre_cajero'] if caj_data else "Desconocido"

        subtotal = 0.0
        detalles_ticket = []

        for item in carrito:
            id_prod = item['id']
            cant = int(item['cantidad'])

            prod_data = db.productos.find_one({"_id": ObjectId(id_prod)}) if ObjectId.is_valid(id_prod) else None
            
            if prod_data:
                nombre_prod = prod_data['nombre_producto']
                precio_unit = float(prod_data['precio'])
                importe = precio_unit * cant
                subtotal += importe

                detalles_ticket.append({
                    'id_prod': ObjectId(id_prod),
                    'nombre': nombre_prod,
                    'cantidad': cant,
                    'precio': precio_unit,
                    'importe': importe
                })

        porcentaje_bonificacion = 5.0 if subtotal >= 5000 else 0.0
        monto_descuento = subtotal * (porcentaje_bonificacion / 100.0)
        total = max(0.0, subtotal - monto_descuento)

        for prod in detalles_ticket:
            db.ventas.insert_one({
                "id_producto": prod['id_prod'],
                "id_cliente": ObjectId(id_cli),
                "id_cajero": ObjectId(id_caj),
                "fecha_vta": fecha,
                "cantidad_p": prod['cantidad'],
                "bonificacion": porcentaje_bonificacion,
                "billete_pago": billete
            })
        
        cambio = max(0.0, billete - total)

        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        ancho_pagina, alto_pagina = 595, 842

        p.setFillColor(colors.HexColor("#09090b"))
        p.rect(0, 0, ancho_pagina, alto_pagina, fill=True, stroke=False)

        p.setFillColor(colors.HexColor("#141418"))
        p.setStrokeColor(colors.HexColor("#27272f"))
        p.roundRect(30, 30, ancho_pagina - 60, alto_pagina - 60, 14, fill=True, stroke=True)

        p.setFillColor(colors.HexColor("#6366f1"))
        p.rect(30, alto_pagina - 36, ancho_pagina - 60, 6, fill=True, stroke=False)

        p.setFillColor(colors.HexColor("#fafafa"))
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, alto_pagina - 68, "COMPROBANTE DE VENTA")
        
        p.setFont("Helvetica", 10)
        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.drawString(50, alto_pagina - 86, "Sistema de Gestión Comercial • Ticket Oficial")

        p.setFillColor(colors.HexColor("#a5b4fc"))
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(ancho_pagina - 50, alto_pagina - 68, f"FECHA: {fecha}")

        p.setStrokeColor(colors.HexColor("#27272f"))
        p.line(50, alto_pagina - 102, ancho_pagina - 50, alto_pagina - 102)

        y_info = alto_pagina - 162
        p.setFillColor(colors.HexColor("#0e0e12"))
        p.setStrokeColor(colors.HexColor("#27272f"))
        p.roundRect(50, y_info, ancho_pagina - 100, 48, 8, fill=True, stroke=True)

        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.setFont("Helvetica-Bold", 9.5)
        p.drawString(65, y_info + 29, "CLIENTE:")
        p.setFillColor(colors.HexColor("#fafafa"))
        p.setFont("Helvetica", 10)
        p.drawString(125, y_info + 29, nombre_cliente)

        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.setFont("Helvetica-Bold", 9.5)
        p.drawString(65, y_info + 11, "ATENDIÓ:")
        p.setFillColor(colors.HexColor("#fafafa"))
        p.setFont("Helvetica", 10)
        p.drawString(125, y_info + 11, nombre_cajero)

        y = y_info - 32
        p.setFillColor(colors.HexColor("#6366f1"))
        p.roundRect(50, y - 6, ancho_pagina - 100, 24, 6, fill=True, stroke=False)

        p.setFillColor(colors.HexColor("#fafafa"))
        p.setFont("Helvetica-Bold", 9)
        p.drawString(62, y + 3, "CANT.")
        p.drawString(110, y + 3, "DESCRIPCIÓN DEL ARTÍCULO")
        p.drawRightString(435, y + 3, "P. UNITARIO")
        p.drawRightString(ancho_pagina - 62, y + 3, "TOTAL")

        y -= 26
        p.setFont("Helvetica", 10)
        for idx, prod in enumerate(detalles_ticket):
            if idx % 2 == 1:
                p.setFillColor(colors.HexColor("#0e0e12"))
                p.rect(50, y - 6, ancho_pagina - 100, 20, fill=True, stroke=False)

            p.setFillColor(colors.HexColor("#fafafa"))
            p.drawString(66, y, str(prod['cantidad']))
            p.drawString(110, y, prod['nombre'][:40])
            p.setFillColor(colors.HexColor("#a1a1aa"))
            p.drawRightString(435, y, f"${prod['precio']:,.2f}")
            p.setFillColor(colors.HexColor("#a5b4fc"))
            p.setFont("Helvetica-Bold", 10)
            p.drawRightString(ancho_pagina - 62, y, f"${prod['importe']:,.2f}")
            p.setFont("Helvetica", 10)
            y -= 22

        p.setStrokeColor(colors.HexColor("#27272f"))
        p.line(50, y + 8, ancho_pagina - 50, y + 8)
        y -= 16

        caja_x = 290
        caja_ancho = ancho_pagina - 50 - caja_x
        
        p.setFillColor(colors.HexColor("#0e0e12"))
        p.setStrokeColor(colors.HexColor("#27272f"))
        p.roundRect(caja_x, y - 128, caja_ancho, 138, 8, fill=True, stroke=True)

        p.setFillColor(colors.HexColor("#6366f1"))
        p.rect(caja_x, y - 128, 3, 138, fill=True, stroke=False)

        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.setFont("Helvetica", 10)
        p.drawString(caja_x + 15, y - 12, "Subtotal:")
        p.setFillColor(colors.HexColor("#fafafa"))
        p.drawRightString(ancho_pagina - 62, y - 12, f"${subtotal:,.2f}")

        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.drawString(caja_x + 15, y - 30, f"Bonificación ({porcentaje_bonificacion:g}%):")
        p.setFillColor(colors.HexColor("#34d399") if monto_descuento > 0 else colors.HexColor("#a1a1aa"))
        p.drawRightString(ancho_pagina - 62, y - 30, f"-${monto_descuento:,.2f}")

        p.setStrokeColor(colors.HexColor("#27272f"))
        p.line(caja_x + 15, y - 41, ancho_pagina - 62, y - 41)

        p.setFillColor(colors.HexColor("#fafafa"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(caja_x + 15, y - 59, "TOTAL NETO:")
        p.drawRightString(ancho_pagina - 62, y - 59, f"${total:,.2f}")

        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.setFont("Helvetica", 10)
        p.drawString(caja_x + 15, y - 84, "Efectivo recibido:")
        p.setFillColor(colors.HexColor("#fafafa"))
        p.drawRightString(ancho_pagina - 62, y - 84, f"${billete:,.2f}")

        p.setFillColor(colors.HexColor("#818cf8"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(caja_x + 15, y - 110, "CAMBIO:")
        p.drawRightString(ancho_pagina - 62, y - 110, f"${cambio:,.2f}")

        y_letras = y - 155
        p.setFont("Helvetica-Oblique", 8.5)
        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.drawRightString(ancho_pagina - 50, y_letras, f"Total: {monto_a_letras(total)}")
        p.drawRightString(ancho_pagina - 50, y_letras - 14, f"Efectivo: {monto_a_letras(billete)}")
        p.drawRightString(ancho_pagina - 50, y_letras - 28, f"Cambio: {monto_a_letras(cambio)}")

        p.setStrokeColor(colors.HexColor("#27272f"))
        p.line(50, 75, ancho_pagina - 50, 75)
        p.setFillColor(colors.HexColor("#a1a1aa"))
        p.setFont("Helvetica", 9)
        p.drawCentredString(ancho_pagina / 2, 55, "Gracias por su preferencia • Conserve este comprobante para cualquier aclaración.")

        p.save()
        buffer.seek(0)

        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = 'inline; filename=comprobante_venta.pdf'
        
        return response

    clientes = list(db.clientes.find())
    productos = list(db.productos.find())
    cajeros = list(db.cajeros.find())

    return render_template('nota_venta.html', clientes=clientes, productos=productos, cajeros=cajeros)
