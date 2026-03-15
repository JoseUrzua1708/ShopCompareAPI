from flask import Flask, render_template, request, redirect, flash, jsonify, Response
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, date
import requests
import xml.etree.ElementTree as ET
import os
import random
import certifi
import ssl

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'supersecretkey'

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
# PANEL GENERAL
# ====================================
@app.route('/', methods=['GET', 'POST'])
def panel():
    tiendas = [formatear_doc(t) for t in db.tienda.find()]
    productos = [formatear_doc(p) for p in db.producto.find()]
    sucursales = [formatear_doc(s) for s in db.sucursal.find()]

    if request.method == 'POST':
        tipo = request.form.get("tipo")
        try:
            if tipo == "tienda":
                nombre = request.form['nombre'].strip()
                if not nombre:
                    flash("El nombre no puede estar vacío ❌", "error")
                    return redirect('/')
                db.tienda.insert_one({"nombre": nombre})
                flash("Tienda registrada correctamente ✅", "success")

            elif tipo == "sucursal":
                nombre = request.form['nombre'].strip()
                direccion = request.form['direccion'].strip()
                ciudad = request.form['ciudad'].strip()
                zona = request.form['zona'].strip()
                tienda_id = request.form['tienda_id']

                if not all([nombre, direccion, ciudad, zona]):
                    flash("Todos los campos son obligatorios ❌", "error")
                    return redirect('/')

                db.sucursal.insert_one({
                    "nombre": nombre, "direccion": direccion, 
                    "ciudad": ciudad, "zona": zona, 
                    "tienda_id": ObjectId(tienda_id)
                })
                flash("Sucursal registrada correctamente ✅", "success")

            elif tipo == "producto":
                nombre = request.form['nombre'].strip()
                descripcion = request.form['descripcion'].strip()
                if not nombre or not descripcion:
                    flash("Completa todos los campos ❌", "error")
                    return redirect('/')

                db.producto.insert_one({"nombre": nombre, "descripcion": descripcion})
                flash("Producto registrado correctamente ✅", "success")

            elif tipo == "precio":
                producto_id = request.form['producto_id']
                sucursal_id = request.form['sucursal_id']
                precio_valor = float(request.form['precio'])
                fecha_str = request.form['fecha']
                
                if not all([producto_id, sucursal_id, precio_valor, fecha_str]):
                    flash("Faltan datos ❌", "error")
                    return redirect('/')

                # Guardamos como datetime para poder hacer consultas por rango
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
        return redirect('/')

    return render_template('panel.html', tiendas=tiendas, productos=productos, sucursales=sucursales)

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
            "producto": "$prod.nombre",
            "descripcion": "$prod.descripcion",
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

        # =====================
        # TIENDA
        # =====================
        tienda_doc = {
            "nombre": data["tienda"]
        }

        tienda_id = db.tienda.insert_one(tienda_doc).inserted_id


        # =====================
        # SUCURSAL
        # =====================
        sucursal_doc = {
            "nombre": data["sucursal"]["nombre"],
            "direccion": data["sucursal"]["direccion"],
            "ciudad": data["sucursal"]["ciudad"],
            "zona": data["sucursal"]["zona"],
            "tienda_id": tienda_id
        }

        sucursal_id = db.sucursal.insert_one(sucursal_doc).inserted_id


        # =====================
        # PRODUCTOS
        # =====================
        for prod in data["productos"]:

            producto_doc = {
                "nombre": prod["nombre"],
                "descripcion": prod["descripcion"]
            }

            producto_id = db.producto.insert_one(producto_doc).inserted_id


            precio_doc = {
                "producto_id": producto_id,
                "sucursal_id": sucursal_id,
                "precio": prod["precio"]
            }

            db.precio.insert_one(precio_doc)


        return jsonify({"mensaje": "JSON importado correctamente"})


    except Exception as e:
        return jsonify({"mensaje": str(e)})

if __name__ == '__main__':
    app.run(debug=True)