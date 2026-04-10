import streamlit as st
import pandas as pd
from datetime import datetime, date

def show():
    if "user_role" not in st.session_state or st.session_state.user_role != "Contador":
        st.error("No tienes permisos para ver el Panel Contable.")
        st.stop()

    st.title("💼 Panel Contable e Impuestos")
    st.markdown("Revisión de flujo de activos, cobros, pasivos y retenciones de IVA.")

    from database import DatabaseHandler
    db = DatabaseHandler()

    # Data completa de Ventas
    df_todas = db.obtener_tabla_ventas_completa()
    # Data completa de Abonos
    df_abonos = db.leer_abonos()

    if df_todas.empty:
        st.info("Aún no hay ventas registradas en el sistema comercial.")
        return

    st.markdown("---")
    st.subheader("Filtro Fiscal (Por Fecha de Venta)")
    
    # Checkbox para habilitar o no la fecha
    usar_filtro_fecha = st.checkbox("Filtrar Análisis por Rango de Fechas", value=False)
    
    if usar_filtro_fecha:
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha Inicio", value=date.today().replace(day=1))
        with col2:
            fecha_fin = st.date_input("Fecha Fin", value=date.today())
            
        # Filtrado
        # Asegurar que df_todas['Fecha_Venta'] es datetime
        df_todas['Fecha_Venta'] = pd.to_datetime(df_todas['Fecha_Venta'])
        mask = (df_todas['Fecha_Venta'] >= pd.to_datetime(fecha_inicio)) & (df_todas['Fecha_Venta'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
        df_filtrado = df_todas.loc[mask].copy()
    else:
        df_filtrado = df_todas.copy()

    # Cálculo Global con lo filtrado
    ventas_totales_brutas = df_filtrado['Total_Venta'].sum()
    iva_16 = df_filtrado['IVA_(16%)'].sum()
    cogs_total = df_filtrado['Costo_Producto'].sum()
    utilidad_neta = df_filtrado['Utilidad_Neta'].sum()
    
    # Comisiones generadas pueden tener comision_red tambien
    comisiones_totales = df_filtrado['Comision_Generada'].sum()
    if 'Comision_Red' in df_filtrado.columns:
        comisiones_totales += df_filtrado['Comision_Red'].sum()

    st.markdown("### Resumen Fiscal (Total Global Histórico o Filtrado)")
    st.markdown("Estas métricas desglosan todo lo que la empresa HA VENDIDO (Bruto). No representa efectivo forzosamente cobrado.")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Ventas Totales Brutas", f"${ventas_totales_brutas:,.2f}")
    with c2:
        st.metric("IVA Reservado (16%)", f"${iva_16:,.2f}")
    with c3:
        st.metric("Costo Deducción (COGS)", f"${cogs_total:,.2f}")
    with c4:
        st.metric("Utilidad Neta (Libre)", f"${utilidad_neta:,.2f}")

    st.markdown("---")
    
    st.markdown("### Resumen de Flujo de Efectivo (Solo Cobrado)")
    if not df_abonos.empty:
        total_abonado = df_abonos['monto_abono'].sum()
    else:
        total_abonado = 0.0

    st.markdown(f"> **El efectivo neto que ha entrado físicamente en bancos/caja asciende a:** `${total_abonado:,.2f}`")
    st.markdown("> **Nota:** El efectivo entrante (Abonos) no se filtra por el calendario superior. El calendario filtra el momento en que se generó la remisión.")
    
    st.markdown("---")
    
    st.markdown("### Exportación de Transacciones / Archivo Master (Excel/CSV)")
    st.markdown("Pasa el ratón sobre la esquina superior derecha de la tabla y da clic en el icono de descarga para bajar el archivo a un CSV.")
    
    # Preparamos las columnas que sirven en contabilidad
    columnas_contables = [
        "ID_Venta", "Fecha_Venta", "Cliente", "Producto", 
        "Costo_Producto", "IVA_(16%)", "Total_Venta", "Comision_Generada", "Utilidad_Neta"
    ]
    # Filtrar solo columnas existentes (por si alguna falta)
    columnas_contables = [c for c in columnas_contables if c in df_filtrado.columns]
    
    df_export = df_filtrado[columnas_contables].copy()
    
    # Formateo visual
    for col in ["Costo_Producto", "IVA_(16%)", "Total_Venta", "Comision_Generada", "Utilidad_Neta"]:
        if col in df_export.columns:
            df_export[col] = df_export[col].map("${:,.2f}".format)
        
    st.dataframe(df_export, use_container_width=True, height=500)
