"""
Sistema MCC - Sistema de Cálculo de Precios
Versión 2.0 - Simplificado para Render
"""
import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify, request  # Importar request aquí
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-123')
CORS(app)

# Configuración de base de datos
def init_db():
    """Inicializa la base de datos SQLite"""
    conn = sqlite3.connect('mcc_sistema.db')
    cursor = conn.cursor()
    
    # Tabla de cálculos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            precio_base REAL NOT NULL,
            precio_final REAL NOT NULL,
            usuario TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de usuarios (opcional para futuras expansiones)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            creado TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Inicializar base de datos al inicio
init_db()

def get_db_connection():
    """Crea y retorna una conexión a la base de datos"""
    conn = sqlite3.connect('mcc_sistema.db')
    conn.row_factory = sqlite3.Row  # Permite acceso por nombre de columna
    return conn

# =============== RUTAS DE LA API ===============

@app.route('/')
def home():
    """Página principal del sistema"""
    return jsonify({
        "message": "Sistema MCC - Sistema de Cálculo de Precios",
        "status": "running",
        "version": "2.0",
        "endpoints": {
            "home": "/",
            "health": "/health",
            "estadisticas": "/api/estadisticas",
            "calcular": "/api/calcular (POST)",
            "historial": "/api/historial"
        }
    })

@app.route('/health')
def health():
    """Endpoint para verificar el estado del servicio"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "mcc-sistema"
    })

@app.route('/api/estadisticas', methods=['GET'])
def estadisticas():
    """Retorna estadísticas del sistema"""
    try:
        conn = get_db_connection()
        
        # Total de cálculos
        total = conn.execute('SELECT COUNT(*) FROM calculos').fetchone()[0]
        
        # Último cálculo
        ultimo = conn.execute('''
            SELECT producto, precio_final, fecha 
            FROM calculos 
            ORDER BY fecha DESC 
            LIMIT 1
        ''').fetchone()
        
        conn.close()
        
        resultado = {
            "total_calculos": total,
            "ultimo_calculo": None
        }
        
        if ultimo:
            resultado["ultimo_calculo"] = {
                "producto": ultimo["producto"],
                "precio_final": ultimo["precio_final"],
                "fecha": ultimo["fecha"]
            }
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calcular', methods=['POST'])
def calcular():
    """Calcula el precio final de un producto"""
    try:
        # Obtener datos del request
        data = request.get_json()  # Usar get_json() en lugar de .json
        
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        producto = data.get('producto', 'Producto sin nombre')
        precio_base = float(data.get('precio_base', 0))
        margen = float(data.get('margen', 30))
        
        # Validaciones
        if precio_base <= 0:
            return jsonify({"success": False, "error": "El precio base debe ser mayor a 0"}), 400
        
        if margen < 0:
            return jsonify({"success": False, "error": "El margen no puede ser negativo"}), 400
        
        # Cálculo del precio final
        precio_final = precio_base * (1 + margen / 100)
        
        # Guardar en base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO calculos (producto, precio_base, precio_final, usuario)
            VALUES (?, ?, ?, ?)
        ''', (producto, precio_base, precio_final, 'usuario_sistema'))
        conn.commit()
        conn.close()
        
        # Respuesta exitosa
        return jsonify({
            "success": True,
            "producto": producto,
            "precio_base": precio_base,
            "margen": margen,
            "precio_final": round(precio_final, 2),
            "timestamp": datetime.now().isoformat()
        })
        
    except ValueError as ve:
        return jsonify({"success": False, "error": f"Error en los datos numéricos: {str(ve)}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Error interno: {str(e)}"}), 500

@app.route('/api/historial', methods=['GET'])
def historial():
    """Retorna el historial de cálculos"""
    try:
        conn = get_db_connection()
        
        # Obtener parámetros de paginación
        limite = request.args.get('limite', default=50, type=int)
        pagina = request.args.get('pagina', default=1, type=int)
        offset = (pagina - 1) * limite
        
        # Consulta con paginación
        cursor = conn.execute('''
            SELECT id, producto, precio_base, precio_final, usuario, fecha
            FROM calculos
            ORDER BY fecha DESC
            LIMIT ? OFFSET ?
        ''', (limite, offset))
        
        calculos = cursor.fetchall()
        
        # Contar total para paginación
        total = conn.execute('SELECT COUNT(*) FROM calculos').fetchone()[0]
        
        conn.close()
        
        # Convertir a lista de diccionarios
        historial_list = []
        for calc in calculos:
            historial_list.append({
                "id": calc["id"],
                "producto": calc["producto"],
                "precio_base": calc["precio_base"],
                "precio_final": calc["precio_final"],
                "usuario": calc["usuario"],
                "fecha": calc["fecha"]
            })
        
        return jsonify({
            "success": True,
            "pagina": pagina,
            "limite": limite,
            "total": total,
            "total_paginas": (total + limite - 1) // limite,
            "calculos": historial_list
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/calcular/<int:id>', methods=['GET'])
def obtener_calculo(id):
    """Obtiene un cálculo específico por ID"""
    try:
        conn = get_db_connection()
        
        calculo = conn.execute('''
            SELECT id, producto, precio_base, precio_final, usuario, fecha
            FROM calculos
            WHERE id = ?
        ''', (id,)).fetchone()
        
        conn.close()
        
        if not calculo:
            return jsonify({"success": False, "error": "Cálculo no encontrado"}), 404
        
        return jsonify({
            "success": True,
            "calculo": {
                "id": calculo["id"],
                "producto": calculo["producto"],
                "precio_base": calculo["precio_base"],
                "precio_final": calculo["precio_final"],
                "usuario": calculo["usuario"],
                "fecha": calculo["fecha"]
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# =============== MANEJO DE ERRORES ===============

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint no encontrado",
        "message": "Verifica la URL e intenta nuevamente"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "success": False,
        "error": "Método no permitido",
        "message": "Este endpoint no soporta el método HTTP utilizado"
    }), 405

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Error interno del servidor",
        "message": "Ha ocurrido un error inesperado"
    }), 500

# =============== INICIO DE LA APLICACIÓN ===============

if __name__ == '__main__':
    # Configuración para desarrollo local
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    print(f"=== Sistema MCC v2.0 ===")
    print(f"Iniciando en puerto: {port}")
    print(f"Modo debug: {debug}")
    print(f"URL: http://localhost:{port}")
    print("=========================")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
