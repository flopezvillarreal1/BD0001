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
    return f"({letras} PESOS MEXICANOS {centavos:02d}/100 MXN)"

tienda_bp = Blueprint('tienda', __name__, template_folder='plantillas')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

MONGO_URI = MONGO_URI = "mongodb+srv://flopezvillarreal1_db_user:palabra2010@dmsa.cqsibku.mongodb.net/?retryWrites=true&w=majority"
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

        p.setFillColor(colors.HexColor("#0f172a"))
        p.rect(0, alto_pagina - 85, ancho_pagina, 85, fill=True, stroke=False)

        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 18)
        p.drawString(45, alto_pagina - 42, "COMPROBANTE DE VENTA")
        
        p.setFont("Helvetica", 10)
        p.setFillColor(colors.HexColor("#cbd5e1"))
        p.drawString(45, alto_pagina - 60, "Sistema de Gestión Comercial • Ticket Oficial")

        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 10)
        p.drawRightString(ancho_pagina - 45, alto_pagina - 42, f"FECHA: {fecha}")

        y_info = alto_pagina - 145
        p.setFillColor(colors.HexColor("#f8fafc"))
        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.roundRect(45, y_info, ancho_pagina - 90, 45, 6, fill=True, stroke=True)

        p.setFillColor(colors.HexColor("#334155"))
        p.setFont("Helvetica-Bold", 10)
        p.drawString(60, y_info + 27, "CLIENTE:")
        p.setFont("Helvetica", 10)
        p.drawString(115, y_info + 27, nombre_cliente)

        p.setFont("Helvetica-Bold", 10)
        p.drawString(60, y_info + 10, "ATENDIÓ:")
        p.setFont("Helvetica", 10)
        p.drawString(115, y_info + 10, nombre_cajero)

        y = y_info - 30
        p.setFillColor(colors.HexColor("#1e3a8a"))
        p.rect(45, y - 6, ancho_pagina - 90, 22, fill=True, stroke=False)

        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 9)
        p.drawString(55, y + 2, "CANT.")
        p.drawString(105, y + 2, "DESCRIPCIÓN DEL ARTÍCULO")
        p.drawRightString(440, y + 2, "P. UNITARIO")
        p.drawRightString(ancho_pagina - 55, y + 2, "TOTAL")

        y -= 24
        p.setFont("Helvetica", 10)
        for idx, prod in enumerate(detalles_ticket):
            if idx % 2 == 1:
                p.setFillColor(colors.HexColor("#f1f5f9"))
                p.rect(45, y - 5, ancho_pagina - 90, 18, fill=True, stroke=False)

            p.setFillColor(colors.HexColor("#0f172a"))
            p.drawString(60, y, str(prod['cantidad']))
            p.drawString(105, y, prod['nombre'][:42])
            p.drawRightString(440, y, f"${prod['precio']:,.2f}")
            p.drawRightString(ancho_pagina - 55, y, f"${prod['importe']:,.2f}")
            y -= 20

        p.setStrokeColor(colors.HexColor("#94a3b8"))
        p.line(45, y + 10, ancho_pagina - 45, y + 10)
        y -= 15

        caja_x = 295
        caja_ancho = ancho_pagina - 45 - caja_x
        
        p.setFillColor(colors.HexColor("#f8fafc"))
        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.roundRect(caja_x, y - 125, caja_ancho, 135, 6, fill=True, stroke=True)

        p.setFillColor(colors.HexColor("#475569"))
        p.setFont("Helvetica", 10)
        p.drawString(caja_x + 15, y - 12, "Subtotal:")
        p.drawRightString(ancho_pagina - 58, y - 12, f"${subtotal:,.2f}")

        p.drawString(caja_x + 15, y - 30, f"Bonificación ({porcentaje_bonificacion:g}%):")
        p.setFillColor(colors.HexColor("#0f766e") if monto_descuento > 0 else colors.HexColor("#475569"))
        p.drawRightString(ancho_pagina - 58, y - 30, f"-${monto_descuento:,.2f}")

        p.setStrokeColor(colors.HexColor("#cbd5e1"))
        p.line(caja_x + 15, y - 40, ancho_pagina - 58, y - 40)

        p.setFillColor(colors.HexColor("#0f172a"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(caja_x + 15, y - 58, "TOTAL NETO:")
        p.drawRightString(ancho_pagina - 58, y - 58, f"${total:,.2f}")

        p.setFillColor(colors.HexColor("#334155"))
        p.setFont("Helvetica", 10)
        p.drawString(caja_x + 15, y - 82, "Efectivo recibido:")
        p.drawRightString(ancho_pagina - 58, y - 82, f"${billete:,.2f}")

        p.setFillColor(colors.HexColor("#1e3a8a"))
        p.setFont("Helvetica-Bold", 12)
        p.drawString(caja_x + 15, y - 108, "CAMBIO:")
        p.drawRightString(ancho_pagina - 58, y - 108, f"${cambio:,.2f}")

        y_letras = y - 150
        p.setFont("Helvetica-Oblique", 8.5)
        p.setFillColor(colors.HexColor("#475569"))
        p.drawRightString(ancho_pagina - 45, y_letras, f"Total: {monto_a_letras(total)}")
        p.drawRightString(ancho_pagina - 45, y_letras - 14, f"Efectivo: {monto_a_letras(billete)}")
        p.drawRightString(ancho_pagina - 45, y_letras - 28, f"Cambio: {monto_a_letras(cambio)}")

        p.setStrokeColor(colors.HexColor("#e2e8f0"))
        p.line(45, 65, ancho_pagina - 45, 65)
        p.setFillColor(colors.HexColor("#64748b"))
        p.setFont("Helvetica", 9)
        p.drawCentredString(ancho_pagina / 2, 48, "Gracias por su preferencia • Conserve este comprobante para cualquier aclaración.")

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