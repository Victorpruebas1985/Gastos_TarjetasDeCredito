import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import altair as alt
from PIL import Image
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from io import BytesIO

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Control de Gastos", layout="wide")
DB_NAME = "mis_finanzas.db"

# --------------------------------------------------------------------------
# TU CLAVE DE API
# --------------------------------------------------------------------------
# Intenta leer de los secretos de Streamlit, si no, usa una vacía (para evitar errores locales si no configuras secrets.toml)
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except:
    # Opción de respaldo solo para pruebas locales rápidas (no recomendado en producción)
    API_KEY = "AIzaSyDTmiXEXztkWLoAxJUd4YM3TUCR1ybm-dk"

# Configurar Gemini
try:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
except Exception as e:
    st.error(f"Error configurando la API: {e}")

# --- FUNCIONES DE BASE DE DATOS ---
def get_connection():
    return sqlite3.connect(DB_NAME)

def guardar_lote_gastos(df_confirmado, fecha_inicio_resumen):
    conn = get_connection()
    c = conn.cursor()
    guardados = 0
    duplicados = 0
    
    if isinstance(fecha_inicio_resumen, str):
        fecha_dt = datetime.strptime(fecha_inicio_resumen, "%Y-%m-%d")
    elif isinstance(fecha_inicio_resumen, datetime):
        fecha_dt = fecha_inicio_resumen
    else:
        fecha_dt = datetime.combine(fecha_inicio_resumen, datetime.min.time())
    
    fecha_str_db = fecha_dt.strftime("%Y-%m-%d")

    for _, row in df_confirmado.iterrows():
        c.execute('''
            SELECT id FROM compras 
            WHERE concepto = ? AND valor_cuota = ? AND fecha_registro = ?
        ''', (row['Concepto'], row['Monto'], fecha_str_db))
        
        existe = c.fetchone()
        
        if existe:
            duplicados += 1
        else:
            c.execute('''
                INSERT INTO compras (fecha_registro, concepto, categoria, total_cuotas, valor_cuota, es_activo) 
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (fecha_str_db, row['Concepto'], row['Categoria'], row['Total Cuotas'], row['Monto']))
            compra_id = c.lastrowid
            generar_plan_pagos(c, compra_id, row['Cuota Actual'], row['Total Cuotas'], row['Monto'], fecha_dt)
            guardados += 1
        
    conn.commit()
    conn.close()
    return guardados, duplicados

def generar_plan_pagos(cursor, compra_id, cuota_inicial, total_cuotas, monto, fecha_base):
    for i in range(cuota_inicial, total_cuotas + 1):
        meses_offset = i - cuota_inicial
        fecha_pago = fecha_base + relativedelta(months=meses_offset)
        fecha_str = fecha_pago.strftime("%Y-%m")
        cursor.execute('INSERT INTO plan_pagos (compra_id, numero_cuota, fecha_pago, monto) VALUES (?, ?, ?, ?)',
                      (compra_id, i, fecha_str, monto))

def eliminar_compra_db(compra_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM plan_pagos WHERE compra_id = ?", (compra_id,))
    c.execute("DELETE FROM compras WHERE id = ?", (compra_id,))
    conn.commit()
    conn.close()

def actualizar_compra_db(compra_id, nuevo_concepto, nueva_cat, nuevo_monto, nuevas_cuotas, fecha_origen):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        UPDATE compras 
        SET concepto=?, categoria=?, valor_cuota=?, total_cuotas=?
        WHERE id=?
    ''', (nuevo_concepto, nueva_cat, nuevo_monto, nuevas_cuotas, compra_id))
    
    c.execute("DELETE FROM plan_pagos WHERE compra_id = ?", (compra_id,))
    
    if isinstance(fecha_origen, str):
        fecha_dt = datetime.strptime(fecha_origen, "%Y-%m-%d")
    else:
        fecha_dt = fecha_origen

    generar_plan_pagos(c, compra_id, 1, nuevas_cuotas, nuevo_monto, fecha_dt)
    conn.commit()
    conn.close()

def analizar_imagen_con_ia(image):
    prompt = """
    Actúa como experto contable. Analiza este resumen de tarjeta.
    REGLAS:
    1. MONEDA EXTRANJERA: Ignora USD/U$S.
    2. NEGATIVOS: Si ves guion al final ("100-") o "BONIF", es negativo.
    3. PLAN Z: Si dice "Z", asume Cuota 1 de 3.
    4. IGNORAR: Pagos, saldos anteriores.
    
    JSON: [{"Concepto": "T", "Cuota Actual": 1, "Total Cuotas": 1, "Monto": 10.0, "Categoria": "Compartido"}]
    Categorías: "Mio", "Compartido", "Otros".
    """
    try:
        response = model.generate_content([prompt, image])
        texto = response.text.replace("```json", "").replace("```", "").strip()
        return pd.read_json(texto)
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Gastos')
    processed_data = output.getvalue()
    return processed_data

# --- INTERFAZ GRAFICA ---
st.title("💳 Sistema Integral de Gastos")

st.sidebar.header("Menú Principal")
menu = st.sidebar.radio(
    "Selecciona una opción:", 
    ["📊 Reporte Mensual", "🔮 Proyección Futura", "🤖 Cargar con IA", "📝 Carga Manual", "🔧 Gestión y Edición"]
)

# ---------------------------------------------------------
# 1. REPORTE MENSUAL
# ---------------------------------------------------------
if menu == "📊 Reporte Mensual":
    col1, col2 = st.columns([1, 2])
    with col1:
        anio = st.selectbox("Año", [2026, 2027], index=0)
    with col2:
        meses = {"01":"Enero","02":"Febrero","03":"Marzo","04":"Abril","05":"Mayo","06":"Junio","07":"Julio","08":"Agosto","09":"Septiembre","10":"Octubre","11":"Noviembre","12":"Diciembre"}
        mes_key = st.selectbox("Mes", list(meses.keys()), index=1, format_func=lambda x: meses[x])
    
    fecha_sel = f"{anio}-{mes_key}"
    st.markdown(f"### 📅 Reporte: {meses[mes_key]} {anio}")

    conn = get_connection()
    df = pd.read_sql(f"""
        SELECT c.concepto, c.categoria, c.total_cuotas, pp.numero_cuota, pp.monto 
        FROM plan_pagos pp JOIN compras c ON pp.compra_id = c.id 
        WHERE pp.fecha_pago = '{fecha_sel}'
    """, conn)
    conn.close()
    
    if df.empty:
        st.info("No hay datos para este mes.")
    else:
        total_m = df[df['categoria'].isin(['M','Mio'])]['monto'].sum()
        total_c = df[df['categoria'].isin(['C','Compartido'])]['monto'].sum()
        total_o = df[df['categoria'].isin(['O','Otros'])]['monto'].sum()
        
        mitad_c = round(total_c/2, 2)
        parte_tuya = total_m + (total_c - mitad_c)
        total_tarjeta = total_m + total_c + total_o

        col_metric1, col_metric2, col_metric3 = st.columns(3)
        col_metric1.metric("Total Tarjeta (Banco)", f"$ {total_tarjeta:,.2f}")
        col_metric2.metric("A Pagar YO", f"$ {parte_tuya:,.2f}", delta_color="inverse")
        col_metric3.metric("Compartido (Total)", f"$ {total_c:,.2f}")
        
        st.divider()

        df['Restan'] = df['total_cuotas'] - df['numero_cuota']
        st.subheader("1. Detalle Vencimientos")
        df_mostrar = df[['concepto', 'Restan', 'monto', 'categoria']].rename(columns={'concepto':'Concepto','monto':'Valor', 'categoria':'Categoria'})
        st.dataframe(df_mostrar[['Concepto', 'Restan', 'Valor']], use_container_width=True, hide_index=True)

        st.subheader("2. Liquidación Final")
        resumen = [
            {"Item": "(M) Mío", "Total": total_m, "A Pagar YO": total_m},
            {"Item": "(C) Compartido", "Total": total_c, "A Pagar YO": (total_c - mitad_c)},
            {"Item": "(O) Otros", "Total": total_o, "A Pagar YO": 0.0},
            {"Item": "TOTAL FINAL", "Total": total_tarjeta, "A Pagar YO": parte_tuya}
        ]
        df_resumen = pd.DataFrame(resumen)
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)

        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="📥 Descargar Detalle en Excel",
                data=to_excel(df_mostrar),
                file_name=f"Gastos_{mes_key}_{anio}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.divider()
        st.subheader("📊 Análisis Visual")
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            datos_grafico = pd.DataFrame({'Categoria': ['Mío', 'Compartido', 'Otros'], 'Monto': [total_m, total_c, total_o]})
            base = alt.Chart(datos_grafico).encode(theta=alt.Theta("Monto", stack=True))
            pie = base.mark_arc(outerRadius=100).encode(
                color=alt.Color("Categoria"),
                order=alt.Order("Monto", sort="descending"),
                tooltip=["Categoria", "Monto"]
            )
            st.altair_chart(pie, use_container_width=True)
            
        with col_graf2:
            datos_barra = pd.DataFrame({'Concepto': ['Total Tarjeta', 'Mi Bolsillo'], 'Monto': [total_tarjeta, parte_tuya]})
            bar = alt.Chart(datos_barra).mark_bar().encode(x='Concepto', y='Monto', color='Concepto', tooltip=['Concepto', 'Monto'])
            st.altair_chart(bar, use_container_width=True)

# ---------------------------------------------------------
# 2. PROYECCIÓN FUTURA (NUEVO !!!)
# ---------------------------------------------------------
elif menu == "🔮 Proyección Futura":
    st.header("🔮 Futuro de Deudas")
    st.markdown("Así se ven tus compromisos de pago para los próximos meses.")
    
    conn = get_connection()
    # Traemos pagos agrupados por mes, desde HOY en adelante
    mes_actual = datetime.now().strftime("%Y-%m")
    
    df_futuro = pd.read_sql(f"""
        SELECT fecha_pago, SUM(monto) as Total 
        FROM plan_pagos 
        WHERE fecha_pago >= '{mes_actual}'
        GROUP BY fecha_pago 
        ORDER BY fecha_pago ASC
    """, conn)
    conn.close()

    if df_futuro.empty:
        st.success("¡Felicidades! No tienes deudas registradas a futuro.")
    else:
        # Gráfico de Barras de Tendencia
        chart_futuro = alt.Chart(df_futuro).mark_bar(color='#ff7f0e').encode(
            x=alt.X('fecha_pago', title='Mes de Vencimiento'),
            y=alt.Y('Total', title='Monto a Pagar ($)'),
            tooltip=['fecha_pago', 'Total']
        ).properties(height=300)
        
        st.altair_chart(chart_futuro, use_container_width=True)
        
        st.markdown("#### Detalle por Mes")
        st.dataframe(
            df_futuro.style.format({"Total": "$ {:,.2f}"}),
            use_container_width=True
        )

# ---------------------------------------------------------
# 3. CARGA IA
# ---------------------------------------------------------
elif menu == "🤖 Cargar con IA":
    st.header("Carga Inteligente")
    archivo = st.file_uploader("Subir resumen", type=["jpg","png","jpeg"])
    if archivo:
        image = Image.open(archivo)
        st.image(image, width=300)
        if st.button("✨ Analizar"):
            with st.spinner("Leyendo..."):
                df_ia = analizar_imagen_con_ia(image)
                if df_ia is not None: st.session_state['datos_ia'] = df_ia

    if 'datos_ia' in st.session_state:
        df_edit = st.data_editor(st.session_state['datos_ia'], num_rows="dynamic",
                                 column_config={"Categoria": st.column_config.SelectboxColumn(options=["Mio", "Compartido", "Otros"])})
        fecha = st.date_input("Mes del Resumen", datetime.now())
        if st.button("Guardar"):
            guardados, duplicados = guardar_lote_gastos(df_edit, fecha)
            if guardados > 0: st.success(f"✅ Guardados: {guardados}")
            if duplicados > 0: st.warning(f"⚠️ Duplicados omitidos: {duplicados}")
            del st.session_state['datos_ia']

# ---------------------------------------------------------
# 4. MANUAL
# ---------------------------------------------------------
elif menu == "📝 Carga Manual":
    st.header("Carga Manual")
    with st.form("f_manual"):
        c = st.text_input("Concepto")
        col1, col2 = st.columns(2)
        m = col1.number_input("Monto", min_value=0.0)
        cuotas = col2.number_input("Cuotas", min_value=1, value=1)
        cat = st.selectbox("Categoría", ["Mio","Compartido","Otros"])
        f = st.date_input("Fecha Inicio", datetime.now())
        if st.form_submit_button("Guardar"):
            df = pd.DataFrame([{"Concepto":c,"Categoria":cat,"Total Cuotas":cuotas,"Cuota Actual":1,"Monto":m}])
            guardados, duplicados = guardar_lote_gastos(df, f)
            if guardados > 0: st.success("✅ Guardado.")
            elif duplicados > 0: st.error("⚠️ Ya existía.")

# ---------------------------------------------------------
# 5. GESTIÓN
# ---------------------------------------------------------
elif menu == "🔧 Gestión y Edición":
    st.header("🔧 Panel de Control")
    conn = get_connection()
    df_compras = pd.read_sql("SELECT id, fecha_registro, concepto, categoria, total_cuotas, valor_cuota FROM compras ORDER BY id DESC", conn)
    conn.close()

    if not df_compras.empty:
        opciones = df_compras.apply(lambda x: f"ID {x['id']}: {x['concepto']} (${x['valor_cuota']})", axis=1)
        seleccion = st.selectbox("Seleccionar gasto:", opciones)
        id_sel = int(seleccion.split(":")[0].replace("ID ", ""))
        dato = df_compras[df_compras['id'] == id_sel].iloc[0]

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            with st.form("edt"):
                nc = st.text_input("Concepto", value=dato['concepto'])
                ncat = st.selectbox("Categoría", ["Mio","Compartido","Otros"], index=["Mio","Compartido","Otros"].index(dato['categoria']) if dato['categoria'] in ["Mio","Compartido","Otros"] else 0)
                nm = st.number_input("Monto", value=float(dato['valor_cuota']))
                ncu = st.number_input("Cuotas", value=int(dato['total_cuotas']))
                if st.form_submit_button("Actualizar"):
                    actualizar_compra_db(id_sel, nc, ncat, nm, ncu, dato['fecha_registro'])
                    st.success("Actualizado.")
                    st.rerun()
        with c2:
            st.error("Zona Peligrosa")
            if st.button("Eliminar"):
                eliminar_compra_db(id_sel)
                st.rerun()