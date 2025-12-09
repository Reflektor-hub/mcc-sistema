"""
Sistema MCC - Sistema de Cálculo de Precios
Versión 2.0 - Optimizado para producción en Railway
"""
import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
from flask_cors import CORS
import logging
from logging.handlers import RotatingFileHandler
import json
import pandas as pd
from io import BytesIO

# Configuración de la aplicación
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')

# Configuración de CORS para producción
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:*",
            "http://127.0.0.1:*",
            "https://*.railway.app",
            "https://*.up.railway.app"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": True
    }
})

# Configuración del logger para producción
if not os.path.exists('logs'):
    os.makedirs('logs')

file_handler = RotatingFileHandler('logs/mcc_sistema.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Sistema MCC iniciado')

# Configuración de base de datos
def get_db_path():
    """Obtiene la ruta de la base de datos según el entorno"""
    if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('DATABASE_URL'):
        # En Railway/Producción, usa path persistente
        return '/data/mcc_sistema.db' if os.path.exists('/data') else 'mcc_sistema.db'
    return 'mcc_sistema.db'

def init_db():
    """Inicializa la base de datos con las tablas necesarias"""
    db_path = get_db_path()
    
    # Crear directorio si no existe (para Railway)
    if '/' in db_path:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Tabla de cálculos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto TEXT NOT NULL,
            precio_base REAL NOT NULL,
            ieps REAL DEFAULT 0,
            iva REAL DEFAULT 16,
            margen_ganancia REAL DEFAULT 30,
            precio_final REAL NOT NULL,
            ganancia REAL NOT NULL,
            usuario TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabla de fórmulas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS formulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            ieps REAL DEFAULT 0,
            iva REAL DEFAULT 16,
            margen_ganancia REAL DEFAULT 30,
            activa BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de productos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            categoria TEXT,
            precio_referencia REAL,
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT DEFAULT 'usuario',
            activo BOOLEAN DEFAULT 1
        )
    ''')
    
    # Insertar datos por defecto
    cursor.execute('SELECT COUNT(*) FROM formulas')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO formulas (nombre, ieps, iva, margen_ganancia) 
            VALUES 
            ('Fórmula General', 0, 16, 30),
            ('Bebidas Alcohólicas', 30, 16, 40),
            ('Tabacos', 160, 16, 35),
            ('Gasolinas', 5.5, 16, 25),
            ('Alimentos Básicos', 0, 0, 20)
        ''')
    
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()[0] == 0:
        # En producción, deberías usar contraseñas hasheadas con bcrypt
        cursor.execute('''
            INSERT INTO usuarios (username, password_hash, nombre, rol) 
            VALUES ('admin', 'admin123', 'Administrador', 'admin')
        ''')
    
    cursor.execute('SELECT COUNT(*) FROM productos')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO productos (nombre, categoria, precio_referencia) 
            VALUES 
            ('Chocolate Importado', 'Dulces', 50),
            ('Vino Tinto', 'Bebidas', 150),
            ('Cigarros', 'Tabaco', 30),
            ('Gasolina Premium', 'Combustible', 22.5),
            ('Arroz', 'Alimentos', 15)
        ''')
    
    conn.commit()
    conn.close()
    app.logger.info('Base de datos inicializada')

# Inicializar base de datos al iniciar
init_db()

def get_db_connection():
    """Crea y retorna una conexión a la base de datos"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

# Middleware para verificar autenticación
@app.before_request
def require_login():
    """Verifica si el usuario está autenticado para rutas protegidas"""
    allowed_routes = ['login', 'static', 'favicon']
    if request.endpoint and not request.endpoint.startswith('api_'):
        if request.endpoint not in allowed_routes and 'user' not in session:
            return redirect(url_for('login'))

# Rutas principales
@app.route('/')
def index():
    """Redirige al dashboard si está autenticado, sino al login"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Maneja el inicio de sesión"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # En producción, esto debería usar bcrypt para verificar contraseñas hasheadas
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM usuarios WHERE username = ? AND activo = 1',
            (username,)
        ).fetchone()
        conn.close()
        
        if user and user['password_hash'] == password:  # Simplificado para demo
            session['user'] = {
                'id': user['id'],
                'username': user['username'],
                'nombre': user['nombre'],
                'rol': user['rol']
            }
            app.logger.info(f'Usuario {username} inició sesión exitosamente')
            return jsonify({'success': True, 'redirect': url_for('dashboard')})
        
        return jsonify({'success': False, 'message': 'Credenciales incorrectas'})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Cierra la sesión del usuario"""
    if 'user' in session:
        app.logger.info(f"Usuario {session['user']['username']} cerró sesión")
        session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    """Dashboard principal"""
    return render_template('dashboard.html')

@app.route('/calculadora')
def calculadora():
    """Página de la calculadora de precios"""
    return render_template('calculadora.html')

@app.route('/historial')
def historial():
    """Página del historial de cálculos"""
    return render_template('historial.html')

@app.route('/productos')
def productos():
    """Página de gestión de productos"""
    return render_template('productos.html')

@app.route('/reportes')
def reportes():
    """Página de reportes"""
    return render_template('reportes.html')

@app.route('/configuracion')
def configuracion():
    """Página de configuración"""
    return render_template('configuracion.html')

# API Endpoints
@app.route('/api/estadisticas')
def api_estadisticas():
    """Obtiene estadísticas para el dashboard"""
    try:
        conn = get_db_connection()
        
        # Total de cálculos
        total_calculos = conn.execute('SELECT COUNT(*) FROM calculos').fetchone()[0]
        
        # Ganancia total
        ganancia_total = conn.execute('SELECT SUM(ganancia) FROM calculos').fetchone()[0] or 0
        
        # Cálculos hoy
        hoy = datetime.now().strftime('%Y-%m-%d')
        calculos_hoy = conn.execute(
            'SELECT COUNT(*) FROM calculos WHERE DATE(fecha) = ?', (hoy,)
        ).fetchone()[0]
        
        # Producto más calculado
        producto_popular = conn.execute(
            'SELECT producto, COUNT(*) as count FROM calculos GROUP BY producto ORDER BY count DESC LIMIT 1'
        ).fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total_calculos': total_calculos,
            'ganancia_total': round(ganancia_total, 2),
            'calculos_hoy': calculos_hoy,
            'producto_popular': producto_popular['producto'] if producto_popular else 'N/A',
            'producto_popular_count': producto_popular['count'] if producto_popular else 0
        })
    except Exception as e:
        app.logger.error(f'Error en estadísticas: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/historial')
def api_historial():
    """Obtiene el historial de cálculos"""
    try:
        limit = request.args.get('limit', 100)
        page = request.args.get('page', 1)
        offset = (int(page) - 1) * int(limit)
        
        conn = get_db_connection()
        
        # Obtener cálculos
        calculos = conn.execute('''
            SELECT * FROM calculos 
            ORDER BY fecha DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset)).fetchall()
        
        # Total para paginación
        total = conn.execute('SELECT COUNT(*) FROM calculos').fetchone()[0]
        
        conn.close()
        
        # Convertir a lista de diccionarios
        historial_list = []
        for calc in calculos:
            historial_list.append(dict(calc))
        
        return jsonify({
            'success': True,
            'historial': historial_list,
            'total': total,
            'page': int(page),
            'total_pages': (total + int(limit) - 1) // int(limit)
        })
    except Exception as e:
        app.logger.error(f'Error en historial: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/formulas')
def api_formulas():
    """Obtiene todas las fórmulas disponibles"""
    try:
        conn = get_db_connection()
        formulas = conn.execute('SELECT * FROM formulas WHERE activa = 1').fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'formulas': [dict(f) for f in formulas]
        })
    except Exception as e:
        app.logger.error(f'Error en fórmulas: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/productos')
def api_productos():
    """Obtiene todos los productos"""
    try:
        conn = get_db_connection()
        productos = conn.execute('SELECT * FROM productos WHERE activo = 1').fetchall()
        conn.close()
        
        return jsonify({
            'success': True,
            'productos': [dict(p) for p in productos]
        })
    except Exception as e:
        app.logger.error(f'Error en productos: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/calcular', methods=['POST'])
def api_calcular():
    """Realiza un cálculo de precio"""
    try:
        data = request.json
        producto = data.get('producto')
        precio_base = float(data.get('precio_base', 0))
        ieps = float(data.get('ieps', 0))
        iva = float(data.get('iva', 16))
        margen = float(data.get('margen_ganancia', 30))
        
        # Cálculos
        importe_ieps = precio_base * (ieps / 100)
        base_iva = precio_base + importe_ieps
        importe_iva = base_iva * (iva / 100)
        costo_total = precio_base + importe_ieps + importe_iva
        ganancia = costo_total * (margen / 100)
        precio_final = costo_total + ganancia
        
        # Guardar en base de datos
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO calculos 
            (producto, precio_base, ieps, iva, margen_ganancia, precio_final, ganancia, usuario)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            producto, precio_base, ieps, iva, margen, 
            round(precio_final, 2), round(ganancia, 2),
            session['user']['username']
        ))
        
        calc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        app.logger.info(f'Cálculo guardado: ID {calc_id}, Producto: {producto}, Precio: ${precio_final:.2f}')
        
        return jsonify({
            'success': True,
            'id': calc_id,
            'resultado': {
                'precio_base': precio_base,
                'importe_ieps': round(importe_ieps, 2),
                'importe_iva': round(importe_iva, 2),
                'costo_total': round(costo_total, 2),
                'ganancia': round(ganancia, 2),
                'precio_final': round(precio_final, 2),
                'margen_porcentaje': margen
            }
        })
    except Exception as e:
        app.logger.error(f'Error en calcular_precio: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exportar-excel')
def api_exportar_excel():
    """Exporta el historial a Excel"""
    try:
        conn = get_db_connection()
        calculos = conn.execute('SELECT * FROM calculos ORDER BY fecha DESC').fetchall()
        conn.close()
        
        # Convertir a DataFrame
        df = pd.DataFrame([dict(c) for c in calculos])
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Historial', index=False)
        
        output.seek(0)
        
        app.logger.info(f"Usuario {session['user']['username']} exportó reporte Excel")
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'historial_mcc_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )
    except Exception as e:
        app.logger.error(f'Error exportando Excel: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# Rutas de administración
@app.route('/admin/backup')
def admin_backup():
    """Endpoint para crear backup de la base de datos (solo admin)"""
    if session.get('user', {}).get('rol') != 'admin':
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    
    try:
        db_path = get_db_path()
        with open(db_path, 'rb') as f:
            db_data = f.read()
        
        return send_file(
            BytesIO(db_data),
            mimetype='application/octet-stream',
            as_attachment=True,
            download_name=f'mcc_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        )
    except Exception as e:
        app.logger.error(f'Error en backup: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# Ruta para favicon (evita error 404)
@app.route('/favicon.ico')
def favicon():
    return '', 204

# Ruta de salud para Railway
@app.route('/health')
def health_check():
    """Endpoint de salud para monitoreo"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Manejo de errores
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'success': False, 'error': 'Ruta no encontrada'}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Error interno: {str(error)}')
    return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500

# Punto de entrada principal
if __name__ == '__main__':
    # Determinar si estamos en producción
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    
    app.logger.info(f'Iniciando servidor en modo {"desarrollo" if debug else "producción"}')
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
