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

@app.route('/configurac
