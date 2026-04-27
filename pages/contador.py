import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import DatabaseHandler

def show():
    if "user_role" not in st.session_state or st.session_state.user_role != "Contador":
        st.error("No tienes permisos para ver el Panel Contable.")
        st.stop()

    st.title("💼 Panel Contable e Impuestos")
    st.markdown("Revisión de flujo de activos, cobros, pasivos y retenciones de IVA.")

    db = DatabaseHandler()

    # Data completa de Ventas
    df_todas = db.obtener_tabla_ventas_completa()
    # Data completa de Abonos
    df_abonos = db.leer_abonos()

    # Cargar Gastos para asegurar cuadre contable
    df_gastos_full = db.obtener_gastos()

    if df_todas.empty:
        st.info("Aún no hay ventas registradas en el sistema comercial.")
        return

    st.markdown("---")
    st.subheader("Filtro Fiscal (Por Fechas)")
    
    # Checkbox para habilitar o no la fecha
    usar_filtro_fecha = st.checkbox("Filtrar Análisis por Rango de Fechas", value=False)
    
    if usar_filtro_fecha:
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha Inicio", value=date.today().replace(day=1))
        with col2:
            fecha_fin = st.date_input("Fecha Fin", value=date.today())
            
        # Filtrado de Ventas
        df_todas['Fecha_Venta'] = pd.to_datetime(df_todas['Fecha_Venta'])
        mask_v = (df_todas['Fecha_Venta'] >= pd.to_datetime(fecha_inicio)) & (df_todas['Fecha_Venta'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
        df_filtrado = df_todas.loc[mask_v].copy()
        
        # Filtrado de Gastos
        if not df_gastos_full.empty:
            df_gastos_full['Fecha'] = pd.to_datetime(df_gastos_full['Fecha'])
            mask_g = (df_gastos_full['Fecha'] >= pd.to_datetime(fecha_inicio)) & (df_gastos_full['Fecha'] >= pd.to_datetime(fecha_inicio)) & (df_gastos_full['Fecha'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
            df_gastos_filtrado = df_gastos_full.loc[mask_g].copy()
        else:
            df_gastos_filtrado = df_gastos_full.copy()
            
    else:
        df_filtrado = df_todas.copy()
        df_gastos_filtrado = df_gastos_full.copy()

    # Cálculo Global con lo filtrado
    ventas_totales_brutas = df_filtrado['Total_Venta'].sum() if not df_filtrado.empty else 0.0
    iva_16 = df_filtrado['IVA_(16%)'].sum() if not df_filtrado.empty else 0.0
    cogs_total = df_filtrado['Costo_Producto'].sum() if not df_filtrado.empty else 0.0
    utilidad_neta_base = df_filtrado['Utilidad_Neta'].sum() if not df_filtrado.empty else 0.0
    
    total_gastos_opex = df_gastos_filtrado['Monto'].sum() if not df_gastos_filtrado.empty else 0.0
    flujo_libre_real = utilidad_neta_base - total_gastos_opex

    # Comisiones generadas pueden tener comision_red tambien
    comisiones_totales = df_filtrado['Comision_Generada'].sum() if not df_filtrado.empty else 0.0
    if 'Comision_Red' in df_filtrado.columns:
        comisiones_totales += df_filtrado['Comision_Red'].sum()

    st.markdown("### Resumen Fiscal (Cuadre Maestría)")
    st.markdown("Métricas pareadas 1:1 con tabuladores ejecutivos para prevención de discrepancias.")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas Brutas", f"${ventas_totales_brutas:,.2f}", 
              help="El monto total absoluto cobrado por la suma de todas las ventas seleccionadas, sin restar ningún impuesto o deducción.")
              
    c2.metric("IVA (16% Reservado)", f"${iva_16:,.2f}", 
              help="El 16% bloqueado automáticamente para los impuestos. Es dinero que pertenece al SAT y no se contabiliza en las utilidades.")
              
    c3.metric("Inv. Producto (COGS)", f"${cogs_total:,.2f}", 
              help="Costo de Bienes Vendidos (Inversión). Determina el dinero congelado que debe usarse para re-comprarle a los proveedores de perfumes y reponer la mercancía vendida.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    c4, c5, c6 = st.columns(3)
    c4.metric("Comisiones (Red)", f"${comisiones_totales:,.2f}", 
              help="Capital cedido como pago por rendimiento a los Agentes Vendedores, Patrocinadores y multinivel. No es utilidad tuya.")
              
    c5.metric("Utilidad Bruta (Sin Op.)", f"${utilidad_neta_base:,.2f}", 
              help="Tu Dinero Base. Obtenido exclusivamente de restar Impuestos, Costos de Inversión y Comisiones a las Ventas. Aún le faltan descontar los viáticos (Módulo de Gastos).")
              
    c6.metric("Gastos (OPEX)", f"-${total_gastos_opex:,.2f}", 
              help="Gastos de Operatividad: Casetas, viáticos, sueldos administrativos, envíos y otros egresos de la sección de Gastos.")
              
    st.markdown("<br>", unsafe_allow_html=True)
    # Centrar la métrica final de impacto usando columnas vacías a los lados
    _, c_center, _ = st.columns([1, 2, 1])
    c_center.metric("✨ Utilidad Neta Real", f"${flujo_libre_real:,.2f}", delta=f"Eficiencia contable validada", delta_color="normal",
                    help="🔥 EL FLUJO LIBRE EFECTIVO: Es la Utilidad Bruta restando los Gastos de Operación. Es el capital financieramente libre, puro y libre de deudas de la empresa.")

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
        
    st.dataframe(df_export, width="stretch", height=500)
