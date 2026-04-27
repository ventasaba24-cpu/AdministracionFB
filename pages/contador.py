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
        df_todas['Fecha_Venta'] = pd.to_datetime(df_todas['Fecha_Venta'])
    if not df_abonos.empty:
        df_abonos['fecha_abono'] = pd.to_datetime(df_abonos['fecha_abono'])
    if not df_gastos_full.empty:
        df_gastos_full['Fecha'] = pd.to_datetime(df_gastos_full['Fecha'])

    # =================================================================
    # BLOQUE 1: APERTURA (CONGELAMIENTO HISTÓRICO)
    # =================================================================
    st.markdown("## 🏛️ Capital Fijo y Apertura (Bloque Histórico)")
    st.markdown("*Datos congelados anteriores al 1 de Mayo. Constituyen tu base de inversión y cartera vencida de entrada.*")
    
    # 1. Capital Físico
    valor_inventario = db.obtener_valor_inventario()
    
    # 2. Cuentas por Cobrar Legacy
    df_ventas_viejas = df_todas[df_todas['Fecha_Venta'] < FECHA_CORTE] if not df_todas.empty else pd.DataFrame()
    deuda_historica = 0.0
    if not df_ventas_viejas.empty:
        ids_viejos = df_ventas_viejas['ID_Venta'].tolist()
        if not df_abonos.empty:
            abonos_viejos_total = df_abonos[df_abonos['venta_id'].isin(ids_viejos)]['monto_abono'].sum()
        else:
            abonos_viejos_total = 0.0
        deuda_historica = df_ventas_viejas['Total_Venta'].sum() - abonos_viejos_total

    c_hist1, c_hist2 = st.columns(2)
    c_hist1.metric("📦 Capital Físico (Inventario en Bodega)", f"${valor_inventario:,.2f}", 
                   help="Valor neto de tu mercancía multiplicando las existencias físicas (Stock) por tu Costo de Compra privado.")
    c_hist2.metric("💸 Cuentas por Cobrar (Legacy Marzo-Abril)", f"${deuda_historica:,.2f}", 
                   help="El dinero que falta recuperar de todas las deudas contraídas antes de abrir este ejercicio.")

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
            
        mask_v = (df_ventas_nuevas['Fecha_Venta'] >= pd.to_datetime(fecha_inicio)) & (df_ventas_nuevas['Fecha_Venta'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
        df_vn_filt = df_ventas_nuevas.loc[mask_v].copy()
        
        mask_g = (df_gastos_nuevos['Fecha'] >= pd.to_datetime(fecha_inicio)) & (df_gastos_nuevos['Fecha'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
        df_gn_filt = df_gastos_nuevos.loc[mask_g].copy()
        
        mask_a = (df_abonos_nuevos['fecha_abono'] >= pd.to_datetime(fecha_inicio)) & (df_abonos_nuevos['fecha_abono'] <= pd.to_datetime(fecha_fin) + pd.Timedelta(days=1))
        df_an_filt = df_abonos_nuevos.loc[mask_a].copy()
    else:
        df_vn_filt = df_ventas_nuevas.copy()
        df_gn_filt = df_gastos_nuevos.copy()
        df_an_filt = df_abonos_nuevos.copy()

    # Cálculo Global Vigente
    ventas_totales_brutas = df_vn_filt['Total_Venta'].sum() if not df_vn_filt.empty else 0.0
    cogs_total = df_vn_filt['Costo_Producto'].sum() if not df_vn_filt.empty else 0.0
    utilidad_neta_base = df_vn_filt['Utilidad_Neta'].sum() if not df_vn_filt.empty else 0.0
    
    total_gastos_opex = df_gn_filt['Monto'].sum() if not df_gn_filt.empty else 0.0
    flujo_libre_real = utilidad_neta_base - total_gastos_opex

    comisiones_totales = df_vn_filt['Comision_Generada'].sum() if not df_vn_filt.empty else 0.0
    if 'Comision_Red' in df_vn_filt.columns:
        comisiones_totales += df_vn_filt['Comision_Red'].sum()

    # CÁLCULO DE IVA POR FLUJO DE EFECTIVO (NUEVO REQUERIMIENTO)
    total_efectivo_cobrado = df_an_filt['monto_abono'].sum() if not df_an_filt.empty else 0.0
    iva_flujo = (total_efectivo_cobrado / 1.16) * 0.16 if total_efectivo_cobrado > 0 else 0.0

    st.markdown("### Resumen Fiscal (Basado en Flujo)")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas Brutas Generadas", f"${ventas_totales_brutas:,.2f}", 
              help="Suma total de nuevas facturaciones desde el 1 de mayo, se hayan pagado o no.")
              
    c2.metric("💳 Flujo Total Cobrado (Abonos)", f"${total_efectivo_cobrado:,.2f}", 
              help="Dinero real nuevo depositado este mes.")
              
    c3.metric("🔴 IVA Causado SAT (16% de Flujo)", f"${iva_flujo:,.2f}", 
              help="[EXTRACCION LEGAL]: El SAT exige el IVA solo de los depósitos bancarios reales. Esta fórmula extrae el 16% de todos los Abonos cobrados en esta ventana.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    c4, c5, c6 = st.columns(3)
    c4.metric("Deducción de Producto", f"${cogs_total:,.2f}", help="Costo de las unidades que salieron de almacén.")
    c5.metric("Comisiones Cedidas", f"${comisiones_totales:,.2f}", help="Pagos totales a Agentes de ventas.")
    c6.metric("Gastos (OPEX)", f"-${total_gastos_opex:,.2f}", help="Mermas operacionales extraídas del mes.")
              
    st.markdown("<br>", unsafe_allow_html=True)
    _, c_center, _ = st.columns([1, 2, 1])
    c_center.metric("✨ Utilidad Neta Real", f"${flujo_libre_real:,.2f}", delta="P&L Vigente", delta_color="normal",
                    help="La rentabilidad final tras pagar producto, deducciones, comisiones y gastos operativos en las ventas nuevas.")

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
