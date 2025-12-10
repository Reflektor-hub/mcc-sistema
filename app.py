"""
Sistema MCC - Sistema de Cálculo de Precios
Versión 2.0 - Simplificado para Render
"""
import os
import sqlite3
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-123')
CORS(app)

# Configuración de base de datos
def init_db():
    conn = sqlite3.connect('mcc_sistema.db')
    cursor = conn.cursor()
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
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect('mcc_sistema.db')
    conn.row_factory = sqlite3.Row
    return conn

# Rutas básicas
@app.route('/')
def home():
    return jsonify({
        "message": "Sistema MCC v2.0",
        "status": "running",
        "version": "2.0"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/api/estadisticas')
def estadisticas():
    conn = get_db_connection()
    total = conn.execute('SELECT COUNT(*) FROM calculos').fetchone()[0]
    conn.close()
    return jsonify({"total_calculos": total})

@app.route('/api/calcular', methods=['POST'])
def calcular():
    try:
        data = request.json
        producto = data.get('producto', 'Producto')
        precio_base = float(data.get('precio_base', 0))
        margen = float(data.get('margen', 30))
        
        precio_final = precio_base * (1 + margen/100)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO calculos (producto, precio_base, precio_final, usuario)
            VALUES (?, ?, ?, ?)
        ''', (producto, precio_base, precio_final, 'admin'))
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "precio_final": round(precio_final, 2)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
