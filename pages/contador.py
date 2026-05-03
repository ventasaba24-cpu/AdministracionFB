import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import DatabaseHandler

def show():
    if "user_role" not in st.session_state or st.session_state.user_role != "Contador":
        st.error("No tienes permisos para ver el Panel Contable.")
        st.stop()

    st.title("💼 Panel Contable e Impuestos")
    st.markdown("Revisión de flujo de activos, cobros y obligaciones fiscales.")

    db = DatabaseHandler()

    # Data Source Completo
    df_todas = db.obtener_tabla_ventas_completa()
    df_abonos = db.leer_abonos()
    df_gastos_full = db.obtener_gastos()

    # Definición de Frontera Histórica
    FECHA_CORTE = pd.to_datetime("2026-05-01")

    # Estandarización a DateTime
    if not df_todas.empty:
        df_todas['Fecha_Venta'] = pd.to_datetime(df_todas['Fecha_Venta'], dayfirst=True, errors='coerce')
    if not df_abonos.empty:
        df_abonos['fecha_abono'] = pd.to_datetime(df_abonos['fecha_abono'], dayfirst=True, errors='coerce')
    if not df_gastos_full.empty:
        df_gastos_full['Fecha'] = pd.to_datetime(df_gastos_full['Fecha'], dayfirst=True, errors='coerce')

    # =================================================================
    # BLOQUE 1: APERTURA (CONGELAMIENTO HISTÓRICO)
    # =================================================================
    st.markdown("## 🏛️ Capital Fijo y Apertura (Bloque Histórico)")
    st.markdown("*Datos congelados anteriores al 1 de Mayo. Constituyen tu base de inversión y cartera vencida de entrada.*")
    
    # 3. Flujo Histórico y Pasivos
    df_gastos_viejos = df_gastos_full[df_gastos_full['Fecha'] < FECHA_CORTE] if not df_gastos_full.empty else pd.DataFrame()
    gastos_viejos_total = df_gastos_viejos['Monto'].sum() if not df_gastos_viejos.empty else 0.0
    
    st.metric("📉 Gastos Históricos (Quemado)", f"${gastos_viejos_total:,.2f}",
              help="Suma de combustible, viáticos y mermas quemados previo a este arranque.")

    st.markdown("---")

    # =================================================================
    # BLOQUE 2: OPERACIÓN VIGENTE (POST-MAYO)
    # =================================================================
    st.markdown("## 📊 Tablero Financiero Vigente (Operativo)")
    st.markdown("*Cálculo de impuestos y P&L (Estado de Resultados) generado desde el 1 de Mayo.*")

    # Partición de Datos Nuevos
    df_ventas_nuevas = df_todas[df_todas['Fecha_Venta'] >= FECHA_CORTE] if not df_todas.empty else pd.DataFrame()
    df_gastos_nuevos = df_gastos_full[df_gastos_full['Fecha'] >= FECHA_CORTE] if not df_gastos_full.empty else pd.DataFrame()
    df_abonos_nuevos = df_abonos[df_abonos['fecha_abono'] >= FECHA_CORTE] if not df_abonos.empty else pd.DataFrame()

    if df_ventas_nuevas.empty and df_abonos_nuevos.empty:
        st.info("Aún no hay transacciones ni cobros en efectivo en la operación vigente.")
        return

    # Filtros Opcionales de Fecha en la Operación Actual
    usar_filtro_fecha = st.checkbox("Filtrar Vigencia por Rango de Fechas", value=False)
    if usar_filtro_fecha:
        colf1, colf2 = st.columns(2)
        with colf1:
            fecha_inicio = st.date_input("Fecha Inicio", value=date.today().replace(day=1))
        with colf2:
            fecha_fin = st.date_input("Fecha Fin", value=date.today())
            
        if not df_ventas_nuevas.empty:
            mask_v = (df_ventas_nuevas['Fecha_Venta'] >= pd.to_datetime(fecha_inicio)) & (df_ventas_nuevas['Fecha_Venta'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
            df_vn_filt = df_ventas_nuevas.loc[mask_v].copy()
        else:
            df_vn_filt = pd.DataFrame()
            
        if not df_gastos_nuevos.empty:
            mask_g = (df_gastos_nuevos['Fecha'] >= pd.to_datetime(fecha_inicio)) & (df_gastos_nuevos['Fecha'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
            df_gn_filt = df_gastos_nuevos.loc[mask_g].copy()
        else:
            df_gn_filt = pd.DataFrame()
            
        if not df_abonos_nuevos.empty:
            mask_a = (df_abonos_nuevos['fecha_abono'] >= pd.to_datetime(fecha_inicio)) & (df_abonos_nuevos['fecha_abono'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
            df_an_filt = df_abonos_nuevos.loc[mask_a].copy()
        else:
            df_an_filt = pd.DataFrame()
    else:
        df_vn_filt = df_ventas_nuevas.copy()
        df_gn_filt = df_gastos_nuevos.copy()
        df_an_filt = df_abonos_nuevos.copy()

    # Cálculo Global Vigente
    total_gastos_opex = df_gn_filt['Monto'].sum() if not df_gn_filt.empty else 0.0

    # CÁLCULO DE IVA POR FLUJO DE EFECTIVO (NUEVO REQUERIMIENTO)
    total_efectivo_cobrado = df_an_filt['monto_abono'].sum() if not df_an_filt.empty else 0.0
    iva_flujo = (total_efectivo_cobrado / 1.16) * 0.16 if total_efectivo_cobrado > 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("💳 Flujo Total Cobrado (Abonos)", f"${total_efectivo_cobrado:,.2f}", 
              help="Dinero real nuevo depositado este mes.")
              
    c2.metric("🔴 IVA Causado SAT (16% de Flujo)", f"${iva_flujo:,.2f}", 
              help="[EXTRACCION LEGAL]: El SAT exige el IVA solo de los depósitos bancarios reales. Esta fórmula extrae el 16% de todos los Abonos cobrados en esta ventana.")
              
    c3.metric("📉 Gastos (OPEX)", f"-${total_gastos_opex:,.2f}", 
              help="Mermas operacionales extraídas del mes.")

    st.markdown("---")
    
    # =================================================================
    # EXPORTACIÓN EXCEL MAESTRO (LIMPIO)
    # =================================================================
    st.markdown("### Exportación de Transacciones (Solo Operativo)")
    st.markdown("Tabla saneada y limpia para uso del contador, excluida de data histórica de abril.")
    
    if not df_vn_filt.empty:
        columnas_contables = [
            "ID_Venta", "Fecha_Venta", "Cliente", "Producto", 
            "Costo_Producto", "IVA_(16%)", "Total_Venta", "Comision_Generada", "Utilidad_Neta"
        ]
        columnas_contables = [c for c in columnas_contables if c in df_vn_filt.columns]
        df_export = df_vn_filt[columnas_contables].copy()
        
        for col in ["Costo_Producto", "IVA_(16%)", "Total_Venta", "Comision_Generada", "Utilidad_Neta"]:
            if col in df_export.columns:
                df_export[col] = df_export[col].map("${:,.2f}".format)
            
        st.dataframe(df_export, width="stretch", height=500)
    else:
        st.caption("Aún no hay desglose descargable en la franja operativa actual.")
