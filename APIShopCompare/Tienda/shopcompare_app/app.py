from flask import Flask, render_template, request, redirect, flash, jsonify, Response, session, url_for, wrappers
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, date
import requests
import xml.etree.ElementTree as ET
import os
from flask_cors import CORS
import random
from functools import wraps
import certifi
import secrets
import ssl

################################################################################
# El que sea encontrado manoseando el BackEnd sera MANOSEADO de la misma forma
# ATENTAMENTE: JOSE DESARROLLADOR BACKEND
################################################################################

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'supersecretkey'

# ====================================
# apy key
# ====================================
def generar_api_key():
    return secrets.token_hex(32)

# ====================================
# Configurar cerrar sesión
# ====================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ==========================================
# CONFIGURACIÓN MONGODB
# ==========================================
# REEMPLAZA ESTO por la URI real de tu clúster en Atlas (Data Explorer -> Connect)
MONGO_URI = "mongodb+srv://202404040_db_user:4ofuYQWDb7r4zQiN@shopcompareapi.syrzi4h.mongodb.net/"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['ShopCompare'] # Conectamos a tu base de datos en Atlas

API_TOKEN = os.getenv("SHOPCOMPARE_API_TOKEN", "shopcompare-dev-token")
MAX_PER_PAGE = 100
app.config["API_REQUIRE_TOKEN"] = False

# ==========================================
# FUNCIONES DE AYUDA Y UTILIDADES
# ==========================================
def formatear_doc(doc):
    """Convierte _id de Mongo a string y renombra la llave a 'id' para el frontend"""
    if doc and '_id' in doc:
        doc['id'] = str(doc.pop('_id'))
    # Formatear otros ObjectIds a string
    for key in ['tienda_id', 'producto_id', 'sucursal_id']:
        if key in doc and isinstance(doc[key], ObjectId):
            doc[key] = str(doc[key])
    return doc

def _agregar_xml(parent, key, value):
    tag = "item" if key is None else str(key)
    elem = ET.SubElement(parent, tag)
    if isinstance(value, dict):
        for k, v in value.items():
            _agregar_xml(elem, k, v)
    elif isinstance(value, list):
        for item in value:
            _agregar_xml(elem, "item", item)
    elif value is None:
        elem.text = ""
    else:
        elem.text = str(value)

def respuesta_api(data, root_tag="response"):
    formato = (request.args.get("format", "json") or "json").lower()
    accept = (request.headers.get("Accept") or "").lower()
    usar_xml = formato == "xml" or ("application/xml" in accept and formato != "json")

    if usar_xml:
        root = ET.Element(root_tag)
        if isinstance(data, dict):
            for k, v in data.items():
                _agregar_xml(root, k, v)
        elif isinstance(data, list):
            for item in data:
                _agregar_xml(root, "item", item)
        else:
            _agregar_xml(root, "value", data)

        xml_bytes = ET.tostring(root, encoding="utf-8")
        return Response(xml_bytes, mimetype="application/xml")
    return jsonify(data)

def token_request():
    token_header = (request.headers.get("X-API-Key") or "").strip()
    auth_header = (request.headers.get("Authorization") or "").strip()
    if token_header:
        return token_header
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""

def validar_token():
    if not app.config.get("API_REQUIRE_TOKEN", False):
        return True
    return token_request() == API_TOKEN

def paginacion():
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        per_page = 20

    page = max(1, page)
    per_page = max(1, min(per_page, MAX_PER_PAGE))
    offset = (page - 1) * per_page
    return page, per_page, offset

def respuesta_paginada(items, total, page, per_page):
    total_pages = (total + per_page - 1) // per_page if total > 0 else 0
    return {
        "data": items,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1 and total_pages > 0
        }
    }

# ====================================
# CONSUMIR APIs EXTERNAS
# ====================================

# funcion para evitar duplicados, y en caso de axistir actualizar el contenido

def obtener_productos_fakestore():
    url = "https://fakestoreapi.com/products"
    try:
        response = requests.get(url, timeout=15)

        if response.status_code == 200:
            return response.json()

    except Exception as e:
        print("Error FakeStore:", e)

    return []


# ================================
# OBTENER PRODUCTOS DE DUMMYJSON
# ================================
def obtener_productos_dummy():
    url = "https://dummyjson.com/products"
    try:
        response = requests.get(url, timeout=15)

        if response.status_code == 200:
            return response.json().get("products", [])

    except Exception as e:
        print("Error DummyJSON:", e)

    return []


# ================================
# COMBINAR PRODUCTOS
# ================================
def combinar_productos():

    productos_final = []

    fakestore = obtener_productos_fakestore()
    dummy = obtener_productos_dummy()

    # FakeStore
    for p in fakestore:

        productos_final.append({
            "titulo": p.get("title"),
            "descripcion": p.get("description"),
            "precio": p.get("price"),
            "categoria": p.get("category"),
            "fuente": "FakeStore"
        })

    # DummyJSON
    for p in dummy:

        productos_final.append({
            "titulo": p.get("title"),
            "descripcion": p.get("description"),
            "precio": p.get("price"),
            "categoria": p.get("category"),
            "fuente": "DummyJSON"
        })

    return productos_final


# ================================
# API
# ================================
@app.route("/api/ver_productos")
def api_ver_productos():

    productos = combinar_productos()

    if len(productos) == 0:
        return jsonify({
            "mensaje": "No llegaron productos de APIs externas"
        })

    return jsonify({
        "total": len(productos),
        "productos": productos
    })

# ====================================
# panel visitante
# ====================================
@app.route("/panel-visitante")
def panel_visitante():
    return render_template("Panel_visitante.html")

# ====================================
# Login 
# ====================================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        correo = request.form.get("correo")
        password = request.form.get("password")

        # buscar usuario
        user = db.usuario.find_one({"correo": correo})

        if not user:
            flash("El correo no está registrado ⚠️", "warning")
            return redirect("/login")

        # verificar contraseña
        if user["password"] != password:
            flash("Correo o contraseña incorrectos ❌", "error")
            return redirect("/login")

        # buscar rol
        rol = db.rol.find_one({"_id": user["rol_id"]})

        session["user"] = {
            "id": str(user["_id"]),
            "correo": user["correo"],
            "rol": rol["nombre"]
        }

        # redireccionar según rol
        if rol["nombre"] == "admin":
            return redirect("/")

        elif rol["nombre"] == "cliente":
            return redirect("/consumir_api")

        else:
            return redirect("/")

    return render_template("login.html")

# ====================================
# REGISTRO
# ====================================

@app.route("/registro", methods=["GET","POST"])
def registro():

    if request.method == "POST":

        nombre = request.form.get("nombre")
        correo = request.form.get("correo")
        password = request.form.get("password")
        confirmar = request.form.get("confirmar")

        # validar campos
        if not nombre or not correo or not password or not confirmar:
            flash("Todos los campos son obligatorios ❌", "error")
            return redirect("/registro")

        # validar contraseñas
        if password != confirmar:
            flash("Las contraseñas no coinciden ❌", "error")
            return redirect("/registro")

        # verificar si el correo ya existe
        usuario_existente = db.usuario.find_one({"correo": correo})

        if usuario_existente:
            flash("El correo ya existe ❌", "error")
            return redirect("/registro")

        # obtener rol cliente
        rol_cliente = db.rol.find_one({"nombre": "cliente"})

        if not rol_cliente:
            flash("Error: rol cliente no encontrado c", "warning")
            return redirect("/registro")

        # insertar usuario
        nuevo_usuario = {
            "nombre": nombre,
            "correo": correo,
            "password": password,
            "rol_id": rol_cliente["_id"],
            "fecha_creacion": datetime.now()
        }

        db.usuario.insert_one(nuevo_usuario)

        flash("Registro exitoso, ahora puedes iniciar sesión ✅", "success")
        return redirect("/login")

    return render_template("registro.html")

# ====================================
# RECUPERAR CONTRASEÑA
# ====================================
@app.route('/recuperar_password')
def recuperar_password():
    return render_template('recuperar_password.html')

# ====================================
# api key
# ====================================
@app.route("/consumir_api", methods=["GET"])
def consumir_api():

    # Si la petición viene con API KEY → devolver JSON
    api_key_header = request.headers.get("API-Key")

    if api_key_header:

        consumo = db.consumos.find_one({"api_key": api_key_header})

        if not consumo:
            return jsonify({"error": "API KEY inválida"}), 403

        precios = list(db.precio.find({}, {"_id": 0}))
        productos = list(db.producto.find({}, {"_id": 0}))
        sucursales = list(db.sucursal.find({}, {"_id": 0}))
        tiendas = list(db.tienda.find({}, {"_id": 0}))

        return jsonify({
            "precio": precios,
            "producto": productos,
            "sucursal": sucursales,
            "tienda": tiendas
        })

    # Si no hay API KEY → mostrar página con la API Key del usuario
    usuario_id = session["user"]["id"]
    usuario_oid = ObjectId(usuario_id)

    consumo = db.consumos.find_one({"usuario_id": usuario_oid})

    if consumo:
        api_key = consumo["api_key"]
    else:
        api_key = generar_api_key()

        db.consumos.insert_one({
            "usuario_id": usuario_oid,
            "api_key": api_key,
            "fecha_creacion": datetime.now()
        })

    return render_template("consumir_api.html", api_key=api_key)

# ====================================
# API JSON CATALOGO
# ====================================
@app.route("/api/catalogo_json", methods=["GET"])
def api_catalog_json():

    api_key = request.headers.get("API-Key")

    consumo = db.consumos.find_one({"api_key": api_key})

    if not consumo:
        return jsonify({"error": "API KEY inválida"}), 403

    precios = list(db.precio.find({}, {"_id": 0}))
    productos = list(db.producto.find({}, {"_id": 0}))
    sucursales = list(db.sucursal.find({}, {"_id": 0}))
    tiendas = list(db.tienda.find({}, {"_id": 0}))

    return jsonify({
        "precio": precios,
        "producto": productos,
        "sucursal": sucursales,
        "tienda": tiendas
    })

# ====================================
# PANEL GENERAL
# ====================================
# -------- DECORADOR PARA PROTEGER RUTAS ADMIN --------
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        # Verificar si el usuario inició sesión
        if "user" not in session:
            flash("Debes iniciar sesión primero ⚠️", "error")
            return redirect(url_for("login"))

        # Verificar si el usuario es admin
        if session["user"].get("rol") != "admin":
            flash("No tienes permisos para acceder a esta página ⚠️", "error")
            return redirect(url_for("panel_visitante"))

        return f(*args, **kwargs)

    return decorated_function


# -------- PANEL ADMIN --------
@app.route('/', methods=['GET', 'POST'])
@admin_required
def panel():

    tiendas = [formatear_doc(t) for t in db.tienda.find()]
    productos = [formatear_doc(p) for p in db.producto.find()]
    sucursales = [formatear_doc(s) for s in db.sucursal.find()]

    if request.method == 'POST':
        tipo = request.form.get("tipo")

        try:

            # -------- REGISTRAR TIENDA --------
            if tipo == "tienda":
                nombre = request.form['nombre'].strip()

                if not nombre:
                    flash("El nombre no puede estar vacío ❌", "error")
                    return redirect(url_for("panel"))

                db.tienda.insert_one({"nombre": nombre})
                flash("Tienda registrada correctamente ✅", "success")


            # -------- REGISTRAR SUCURSAL --------
            elif tipo == "sucursal":
                nombre = request.form['nombre'].strip()
                direccion = request.form['direccion'].strip()
                ciudad = request.form['ciudad'].strip()
                zona = request.form['zona'].strip()
                tienda_id = request.form['tienda_id']

                if not all([nombre, direccion, ciudad, zona]):
                    flash("Todos los campos son obligatorios ❌", "error")
                    return redirect(url_for("panel"))

                db.sucursal.insert_one({
                    "nombre": nombre,
                    "direccion": direccion,
                    "ciudad": ciudad,
                    "zona": zona,
                    "tienda_id": ObjectId(tienda_id)
                })

                flash("Sucursal registrada correctamente ✅", "success")


            # -------- REGISTRAR PRODUCTO --------
            elif tipo == "producto":
                nombre = request.form['nombre'].strip()
                descripcion = request.form['descripcion'].strip()

                if not nombre or not descripcion:
                    flash("Completa todos los campos ❌", "error")
                    return redirect(url_for("panel"))

                db.producto.insert_one({
                    "nombre": nombre,
                    "descripcion": descripcion
                })

                flash("Producto registrado correctamente ✅", "success")


            # -------- REGISTRAR PRECIO --------
            elif tipo == "precio":

                producto_id = request.form['producto_id']
                sucursal_id = request.form['sucursal_id']
                precio_valor = float(request.form['precio'])
                fecha_str = request.form['fecha']

                if not all([producto_id, sucursal_id, precio_valor, fecha_str]):
                    flash("Faltan datos ❌", "error")
                    return redirect(url_for("panel"))

                fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")

                db.precio.insert_one({
                    "producto_id": ObjectId(producto_id),
                    "sucursal_id": ObjectId(sucursal_id),
                    "precio": precio_valor,
                    "fecha": fecha_dt
                })

                flash("Precio registrado correctamente ✅", "success")

            else:
                flash("Tipo de registro inválido ❌", "error")

        except Exception as e:
            print(e)
            flash("Ocurrió un error al guardar ⚠️", "error")

        return redirect(url_for("panel"))

    return render_template(
        'panel.html',
        tiendas=tiendas,
        productos=productos,
        sucursales=sucursales
    )
# ====================================
# COMPARADOR (VISTA)
# ====================================
@app.route('/comparar')
def comparar():
    try:
        # Reemplazamos el JOIN de SQL con un Aggregation Pipeline de Mongo
        pipeline = [
            {"$lookup": {"from": "producto", "localField": "producto_id", "foreignField": "_id", "as": "prod"}},
            {"$unwind": "$prod"},
            {"$lookup": {"from": "sucursal", "localField": "sucursal_id", "foreignField": "_id", "as": "suc"}},
            {"$unwind": "$suc"},
            {"$lookup": {"from": "tienda", "localField": "suc.tienda_id", "foreignField": "_id", "as": "tnd"}},
            {"$unwind": "$tnd"},
            {"$sort": {"prod.nombre": 1, "precio": 1}},
            {"$project": {
                "producto_nombre": "$prod.nombre", "tienda_nombre": "$tnd.nombre",
                "sucursal_nombre": "$suc.nombre", "ciudad": "$suc.ciudad", "zona": "$suc.zona",
                "precio": 1, "fecha": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha"}}
            }}
        ]
        
        datos_mongo = list(db.precio.aggregate(pipeline))
        
        # Formateamos los datos para que el HTML los lea como una tupla/lista igual que hacía MySQL
        datos = []
        for d in datos_mongo:
            datos.append((d['producto_nombre'], d['tienda_nombre'], d['sucursal_nombre'], 
                          d['ciudad'], d['zona'], d['precio'], d['fecha']))

        return render_template("comparar.html", datos=datos)
    except Exception as e:
        print("Error en vista comparar:", e)
        flash("Error al cargar el comparador ⚠️", "error")
        return redirect('/')

# ====================================
# API PRODUCTOS
# ====================================
@app.route('/api/productos')
def api_productos():
    try:
        productos = [formatear_doc(p) for p in db.producto.find({}, {"nombre": 1, "descripcion": 1})]
        return jsonify(productos)
    except Exception as e:
        print("Error API productos:", e)
        return jsonify({"error": "Error al obtener productos"}), 500

# ====================================
# API COMPARAR PRECIOS
# ====================================
@app.route('/api/comparar-precios')
def api_comparar():
    try:
        ciudad = request.args.get("ciudad")
        zona = request.args.get("zona")
        producto = request.args.get("producto")

        match_stage = {}
        if producto: match_stage["producto_id"] = ObjectId(producto)

        pipeline = [{"$match": match_stage}] if match_stage else []
        pipeline.extend([
            {"$lookup": {"from": "producto", "localField": "producto_id", "foreignField": "_id", "as": "prod"}},
            {"$unwind": "$prod"},
            {"$lookup": {"from": "sucursal", "localField": "sucursal_id", "foreignField": "_id", "as": "suc"}},
            {"$unwind": "$suc"},
            {"$lookup": {"from": "tienda", "localField": "suc.tienda_id", "foreignField": "_id", "as": "tnd"}},
            {"$unwind": "$tnd"}
        ])

        # Aplicamos filtros de ciudad y zona después del lookup
        match_sucursal = {}
        if ciudad: match_sucursal["suc.ciudad"] = ciudad
        if zona: match_sucursal["suc.zona"] = zona
        
        if match_sucursal: pipeline.append({"$match": match_sucursal})

        pipeline.extend([
            {"$sort": {"prod.nombre": 1, "precio": 1}},
            {"$project": {
                "producto": "$prod.nombre", "tienda": "$tnd.nombre", "sucursal": "$suc.nombre",
                "ciudad": "$suc.ciudad", "zona": "$suc.zona", "precio": 1, 
                "fecha": {"$dateToString": {"format": "%Y-%m-%d", "date": "$fecha"}}
            }}
        ])

        datos = list(db.precio.aggregate(pipeline))
        for d in datos: d.pop('_id', None) # Limpiamos el ID de la respuesta
        return jsonify(datos)

    except Exception as e:
        print("Error API comparar precios:", e)
        return jsonify({"error": "Error al comparar precios"}), 500

# ====================================
# API TENDENCIA DE PRECIOS
# ====================================
@app.route('/api/tendencia/<id_producto>')
def api_tendencia(id_producto):
    try:
        datos = db.precio.find({"producto_id": ObjectId(id_producto)}).sort("fecha", 1)
        resultado = [{"fecha": d["fecha"].strftime("%Y-%m-%d"), "precio": float(d["precio"])} for d in datos]
        return jsonify(resultado)
    except Exception as e:
        print("Error API tendencia:", e)
        return jsonify({"error": "Error al obtener tendencia"}), 500

# ====================================
# API PRECIO MAS BARATO
# ====================================
@app.route('/api/precio-mas-barato/<id_producto>')
def precio_mas_barato(id_producto):
    try:
        pipeline = [
            {"$match": {"producto_id": ObjectId(id_producto)}},
            {"$lookup": {"from": "producto", "localField": "producto_id", "foreignField": "_id", "as": "prod"}},
            {"$unwind": "$prod"},
            {"$lookup": {"from": "sucursal", "localField": "sucursal_id", "foreignField": "_id", "as": "suc"}},
            {"$unwind": "$suc"},
            {"$lookup": {"from": "tienda", "localField": "suc.tienda_id", "foreignField": "_id", "as": "tnd"}},
            {"$unwind": "$tnd"},
            {"$sort": {"precio": 1}},
            {"$limit": 1},
            {"$project": {
                "producto": "$prod.nombre", "tienda": "$tnd.nombre", 
                "sucursal": "$suc.nombre", "precio_mas_barato": "$precio", "_id": 0
            }}
        ]
        
        datos = list(db.precio.aggregate(pipeline))
        return jsonify(datos[0] if datos else {"mensaje": "No hay datos"})
    except Exception as e:
        print("Error API precio más barato:", e)
        return jsonify({"error": "Error al obtener el precio más barato"}), 500

# ====================================
# API ANALISIS DE PRODUCTO Y ESTADISTICAS
# ====================================
@app.route('/api/variacion-precios/<id_producto>')
def variacion_precios(id_producto):
    pipeline = [
        {"$match": {"producto_id": ObjectId(id_producto)}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m", "date": "$fecha"}},
            "precio_promedio": {"$avg": "$precio"}
        }},
        {"$sort": {"_id": 1}}
    ]
    datos = db.precio.aggregate(pipeline)
    return jsonify([{"mes": d["_id"], "precio_promedio": round(d["precio_promedio"], 2)} for d in datos])

@app.route('/api/estadisticas-mercado')
def estadisticas_mercado():
    pipeline = [
        {"$lookup": {"from": "sucursal", "localField": "sucursal_id", "foreignField": "_id", "as": "suc"}},
        {"$unwind": "$suc"},
        {"$lookup": {"from": "tienda", "localField": "suc.tienda_id", "foreignField": "_id", "as": "tnd"}},
        {"$unwind": "$tnd"},
        {"$group": {
            "_id": "$tnd.nombre",
            "precio_promedio": {"$avg": "$precio"},
            "precio_minimo": {"$min": "$precio"},
            "precio_maximo": {"$max": "$precio"}
        }}
    ]
    datos = db.precio.aggregate(pipeline)
    resultado = [{
        "tienda": d["_id"], "precio_promedio": round(d["precio_promedio"], 2),
        "precio_minimo": d["precio_minimo"], "precio_maximo": d["precio_maximo"]
    } for d in datos]
    return jsonify(resultado)

@app.route('/api/filtros')
def filtros():
    ciudades = db.sucursal.distinct("ciudad")
    zonas = db.sucursal.distinct("zona")
    return jsonify({"ciudades": ciudades, "zonas": zonas})

# ====================================
# API REST v1
# ====================================
@app.route("/api/v1/catalogo")
def api_catalogo():
    try:
        if not validar_token():
            return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401

        tiendas = [formatear_doc(d) for d in db.tienda.find()]
        sucursales = [formatear_doc(d) for d in db.sucursal.find()]
        productos = [formatear_doc(d) for d in db.producto.find()]
        
        precios = []
        for p in db.precio.find():
            p = formatear_doc(p)
            if isinstance(p["fecha"], datetime):
                p["fecha"] = p["fecha"].strftime("%Y-%m-%d")
            precios.append(p)

        payload = {
            "version": "v1", "tiendas": tiendas, "sucursales": sucursales,
            "productos": productos, "precios": precios,
            "total_tiendas": len(tiendas), "total_sucursales": len(sucursales),
            "total_productos": len(productos), "total_precios": len(precios)
        }
        return respuesta_api(payload, root_tag="catalogo")
    except Exception as e:
        print("Error API catalogo:", e)
        return respuesta_api({"error": "Error al obtener catalogo"}, root_tag="error"), 500

@app.route("/api/v1/tiendas")
def api_v1_tiendas():
    if not validar_token(): return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401
    # Devuelve: id, nombre
    items = [formatear_doc(t) for t in db.tienda.find({}, {"nombre": 1})]
    return jsonify(items)

@app.route("/api/v1/sucursales")
def api_v1_sucursales():
    if not validar_token(): return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401
    # Devuelve: id, nombre, direccion, ciudad, zona, tienda_id
    items = [formatear_doc(s) for s in db.sucursal.find({}, {
        "nombre": 1, "direccion": 1, "ciudad": 1, "zona": 1, "tienda_id": 1
    })]
    return jsonify(items)

@app.route("/api/v1/productos")
def api_v1_productos():
    if not validar_token(): return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401
    # Devuelve: id, nombre, descripcion (MUESTRA TODOS LOS PRODUCTOS, SIN PAGINAR)
    items = [formatear_doc(p) for p in db.producto.find({}, {
        "nombre": 1, "descripcion": 1
    })]
    return jsonify(items)

@app.route("/api/v1/precios")
def api_v1_precios():
    if not validar_token(): return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401
    # Devuelve: id, producto_id, sucursal_id, precio, fecha
    items = []
    for p in db.precio.find({}, {"producto_id": 1, "sucursal_id": 1, "precio": 1, "fecha": 1}):
        p = formatear_doc(p)
        if isinstance(p.get("fecha"), datetime):
            p["fecha"] = p["fecha"].strftime("%Y-%m-%d")
        items.append(p)
    return jsonify(items)

# ====================================
# API EXTRA: TODA LA BD UNIDA (JOIN)
# ====================================
@app.route("/api/v1/completo")
def api_v1_completo():
    if not validar_token(): return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401
    
    # Unimos todo para sacar un solo objeto plano
    pipeline = [
        {"$lookup": {"from": "producto", "localField": "producto_id", "foreignField": "_id", "as": "prod"}},
        {"$unwind": "$prod"},
        {"$lookup": {"from": "sucursal", "localField": "sucursal_id", "foreignField": "_id", "as": "suc"}},
        {"$unwind": "$suc"},
        {"$lookup": {"from": "tienda", "localField": "suc.tienda_id", "foreignField": "_id", "as": "tnd"}},
        {"$unwind": "$tnd"},
        {"$project": {
            "_id": 0,
            "tienda": "$tnd.nombre",
            "sucursal": "$suc.nombre",
            "direccion": "$suc.direccion", # Agregamos direccion
            "ciudad": "$suc.ciudad",       # Agregamos ciudad
            "zona": "$suc.zona",           # Agregamos zona
            "producto": "$prod.nombre",
            "descripcion": "$prod.descripcion",
            "precio": 1
        }}
    ]
    datos = list(db.precio.aggregate(pipeline))
    return jsonify(datos)


# ====================================
# API DE PRUEBA: SOLO FRIJOL (Con datos de Acapulco)
# ====================================
@app.route("/api/v1/ejemplo-frijol")
def api_ejemplo_frijol():
    if not validar_token(): return respuesta_api({"error": "No autorizado"}, root_tag="error"), 401
    
    pipeline = [
        {"$lookup": {"from": "producto", "localField": "producto_id", "foreignField": "_id", "as": "prod"}},
        {"$unwind": "$prod"},
        {"$match": {"prod.nombre": {"$regex": "Frijol", "$options": "i"}}}, # Filtramos por Frijol
        {"$lookup": {"from": "sucursal", "localField": "sucursal_id", "foreignField": "_id", "as": "suc"}},
        {"$unwind": "$suc"},
        {"$lookup": {"from": "tienda", "localField": "suc.tienda_id", "foreignField": "_id", "as": "tnd"}},
        {"$unwind": "$tnd"},
        {"$project": {
            "_id": 0,
            "producto": "$prod.nombre",
            "descripcion": "$prod.descripcion",
            "tienda": "$tnd.nombre",
            "sucursal": "$suc.nombre",
            "direccion": "$suc.direccion",
            "ciudad": "$suc.ciudad",
            "zona": "$suc.zona",
            "precio": 1
        }}
    ]
    datos = list(db.precio.aggregate(pipeline))
    return jsonify(datos)



# ====================================
# APIs EXTERNAS: PREVIEW + SYNC 
# ====================================
def obtener_productos_externos():
    productos = []
    for p in obtener_productos_fakestore():
        nombre = (p.get("title") or "").strip()
        if not nombre: continue
        try: precio = float(p.get("price", 0))
        except (TypeError, ValueError): continue
        productos.append({"fuente": "Amazon", "nombre": nombre, "descripcion": (p.get("description") or "").strip(), "precio": precio})

    for p in obtener_productos_dummy():
        nombre = (p.get("title") or "").strip()
        if not nombre: continue
        try: precio = float(p.get("price", 0))
        except (TypeError, ValueError): continue
        productos.append({"fuente": "Walmart", "nombre": nombre, "descripcion": (p.get("description") or "").strip(), "precio": precio})
    return productos

@app.route("/api/preview-precios")
def preview_precios():
    try:
        productos = obtener_productos_externos()
        return respuesta_api({"total": len(productos), "productos": productos}, root_tag="preview_precios")
    except Exception as e:
        print("Error preview:", e)
        return respuesta_api({"error": "Error al consumir APIs externas"}, root_tag="error"), 500

@app.route("/api/sync-precios", methods=["POST", "GET"])
def sync_precios_api():
    try:
        productos = obtener_productos_externos()
        if not productos:
            return respuesta_api({"error": "No llegaron datos de APIs"}, root_tag="error"), 400

        productos_nuevos = productos_actualizados = precios_insertados = precios_actualizados = 0
        fecha_hoy = datetime.combine(date.today(), datetime.min.time())

        tienda_por_fuente = {}
        for fuente in ("Amazon", "Walmart"):
            # Upsert Tienda
            tienda = db.tienda.find_one_and_update(
                {"nombre": fuente}, {"$setOnInsert": {"nombre": fuente}}, upsert=True, return_document=True)
            
            # Upsert Sucursal
            sucursal = db.sucursal.find_one_and_update(
                {"tienda_id": tienda["_id"], "nombre": "Sucursal Online"},
                {"$setOnInsert": {"direccion": "Internet", "ciudad": "Global", "zona": "Digital"}},
                upsert=True, return_document=True)
            
            tienda_por_fuente[fuente] = sucursal["_id"]

        for p in productos:
            sucursal_id = tienda_por_fuente[p["fuente"]]

            # Verificar/Crear Producto
            prod_existente = db.producto.find_one({"nombre": p["nombre"]})
            if not prod_existente:
                prod_id = db.producto.insert_one({"nombre": p["nombre"], "descripcion": p["descripcion"]}).inserted_id
                productos_nuevos += 1
            else:
                prod_id = prod_existente["_id"]
                if prod_existente.get("descripcion") != p["descripcion"]:
                    db.producto.update_one({"_id": prod_id}, {"$set": {"descripcion": p["descripcion"]}})
                    productos_actualizados += 1

            # Verificar/Crear Precio para HOY
            precio_existente = db.precio.find_one({"producto_id": prod_id, "sucursal_id": sucursal_id, "fecha": fecha_hoy})
            if not precio_existente:
                db.precio.insert_one({"producto_id": prod_id, "sucursal_id": sucursal_id, "precio": p["precio"], "fecha": fecha_hoy})
                precios_insertados += 1
            else:
                if float(precio_existente["precio"]) != float(p["precio"]):
                    db.precio.update_one({"_id": precio_existente["_id"]}, {"$set": {"precio": p["precio"]}})
                    precios_actualizados += 1

        return respuesta_api({
            "mensaje": "Sincronizacion completada", "total_consultados": len(productos),
            "productos_nuevos": productos_nuevos, "productos_actualizados": productos_actualizados,
            "precios_insertados": precios_insertados, "precios_actualizados": precios_actualizados
        }, root_tag="sync_precios")

    except Exception as e:
        print("Error sincronizando:", e)
        return respuesta_api({"error": "Error al sincronizar"}, root_tag="error"), 500
    

@app.route("/api/importar_json", methods=["POST"])
def importar_json():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No se recibió JSON"}), 400

        productos_a_procesar = data if isinstance(data, list) else [data]
        fecha_hoy = datetime.combine(date.today(), datetime.min.time())
        precios_guardados, productos_procesados = 0, 0

        for item in productos_a_procesar:
            nombre_prod = item.get("producto")
            desc_prod = item.get("descripcion", "")
            disponibilidad = item.get("disponibilidad", [])

            if not nombre_prod or not disponibilidad: continue

            # 1. BUSCAR O CREAR PRODUCTO
            prod_doc = db.producto.find_one({"nombre": nombre_prod})
            if not prod_doc:
                prod_id = db.producto.insert_one({"nombre": nombre_prod, "descripcion": desc_prod}).inserted_id
            else:
                prod_id = prod_doc["_id"]
                db.producto.update_one({"_id": prod_id}, {"$set": {"descripcion": desc_prod}})

            # 2. RECORRER DISPONIBILIDAD CON NUEVOS CAMPOS
            for oferta in disponibilidad:
                t_nombre = oferta.get("tienda")
                s_nombre = oferta.get("sucursal")
                s_dir = oferta.get("direccion", "Dirección no especificada")
                s_ciudad = oferta.get("ciudad", "Acapulco")
                s_zona = oferta.get("zona", "General")
                precio_val = float(oferta.get("precio", 0))

                if not t_nombre or not s_nombre or precio_val <= 0: continue

                tienda_doc = db.tienda.find_one_and_update(
                    {"nombre": t_nombre}, {"$setOnInsert": {"nombre": t_nombre}},
                    upsert=True, return_document=True
                )

                sucursal_doc = db.sucursal.find_one_and_update(
                    {"tienda_id": tienda_doc["_id"], "nombre": s_nombre},
                    {"$setOnInsert": {"direccion": s_dir, "ciudad": s_ciudad, "zona": s_zona}},
                    upsert=True, return_document=True
                )

                precio_existente = db.precio.find_one({
                    "producto_id": prod_id, "sucursal_id": sucursal_doc["_id"], "fecha": fecha_hoy
                })
                
                if not precio_existente:
                    db.precio.insert_one({
                        "producto_id": prod_id, "sucursal_id": sucursal_doc["_id"], 
                        "precio": precio_val, "fecha": fecha_hoy
                    })
                else:
                    db.precio.update_one({"_id": precio_existente["_id"]}, {"$set": {"precio": precio_val}})
                
                precios_guardados += 1
            productos_procesados += 1

        return jsonify({"mensaje": f"¡Éxito! {productos_procesados} productos y {precios_guardados} precios actualizados."})

    except Exception as e:
        print("Error importando JSON:", e)
        return jsonify({"error": "Error al procesar el JSON."}), 500

# ====================
# run app
# ====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render asigna el puerto
    app.run(host="0.0.0.0", port=port, debug=True)