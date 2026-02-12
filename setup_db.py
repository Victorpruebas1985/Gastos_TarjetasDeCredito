import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Nombre de la base de datos
DB_NAME = "mis_finanzas.db"

# --- DATOS INICIALES (TU FOTO DE FEBRERO 2026) ---
# Formato: (Concepto, Categoría, Cuotas QUE RESTAN VISUALMENTE, Monto Cuota)
# NOTA: Para que la matemática (Total - Actual) de exacto lo que ves en el Excel,
# sumaremos 1 al total en la carga inicial, asumiendo que estamos en la cuota 1 de este periodo.
datos_iniciales = [
    ("DREAN SA",           "O", 13, 37373.26),
    ("FRAVEGA.COM-BNA",    "C", 3,  33333.16),
    ("GADNIC",             "C", 3,  23118.16),
    ("TIENDABNA.COM.AR",   "C", 21, 12187.45),
    ("VISAUR",             "C", 9,  5000.00),
    ("TOTAL HOME S.A.",    "C", 21, 3031.20),
    ("BIDCOM",             "C", 9,  2778.58),
    ("TIO MUSA SA",        "C", 21, 2345.50),
    ("DEPOT CENTER",       "C", 9,  2374.95),
    ("STYLE STORE",        "C", 1,  2166.66),
    ("FARMACIA SANTA ANA", "M", 2,  11848.58),
    ("YENNY CORRIENTES",   "M", 5,  2416.66)
]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 1. Tabla de Compras (Maestra) - AHORA CON 'total_cuotas'
    c.execute('''
        CREATE TABLE IF NOT EXISTS compras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_registro TEXT,
            concepto TEXT,
            categoria TEXT, 
            total_cuotas INTEGER, -- <--- ESTA ES LA COLUMNA QUE FALTABA
            valor_cuota REAL,
            es_activo BOOLEAN DEFAULT 1
        )
    ''')

    # 2. Tabla de Plan de Pagos (Detalle mes a mes)
    c.execute('''
        CREATE TABLE IF NOT EXISTS plan_pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compra_id INTEGER,
            numero_cuota INTEGER, -- Para saber si es la 1/12, 2/12...
            fecha_pago TEXT, 
            monto REAL,
            FOREIGN KEY(compra_id) REFERENCES compras(id)
        )
    ''')

    print("--- Tablas creadas. Cargando datos iniciales... ---")

    # Fecha de inicio: FEBRERO 2026
    fecha_base = datetime(2026, 2, 1)

    for item in datos_iniciales:
        concepto, cat, restan, valor = item
        
        # Truco matemático para que la tabla visual coincida:
        # Si te restan 13 cuotas y estamos en el mes 1, definimos el plan como de 14 cuotas totales.
        # Así: 14 (total) - 1 (cuota actual) = 13 (Restan).
        total_cuotas_ajustado = restan + 1
        
        # Insertar en Compras con la nueva columna
        c.execute('''
            INSERT INTO compras (fecha_registro, concepto, categoria, total_cuotas, valor_cuota) 
            VALUES (?, ?, ?, ?, ?)
        ''', (fecha_base.strftime("%Y-%m-%d"), concepto, cat, total_cuotas_ajustado, valor))
        
        compra_id = c.lastrowid

        # Proyectar los pagos futuros
        # Generamos desde la cuota 1 en adelante
        for i in range(1, total_cuotas_ajustado + 1):
            # Calculamos la fecha: Fecha Base + (i-1) meses
            fecha_pago = fecha_base + relativedelta(months=i-1)
            fecha_str = fecha_pago.strftime("%Y-%m") 
            
            c.execute('INSERT INTO plan_pagos (compra_id, numero_cuota, fecha_pago, monto) VALUES (?, ?, ?, ?)',
                      (compra_id, i, fecha_str, valor))

    conn.commit()
    conn.close()
    print("¡Base de datos REPARADA y cargada con éxito!")

if __name__ == "__main__":
    init_db()