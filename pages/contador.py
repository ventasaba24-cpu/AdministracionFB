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
    if not df_gn_filt.empty:
        df_gn_filt['Tiene_Factura'] = df_gn_filt['Tiene_XML'] | df_gn_filt['Tiene_PDF']
        mask_con_factura = df_gn_filt['Tiene_Factura'] == True
        total_gastos_con_factura = df_gn_filt.loc[mask_con_factura, 'Monto'].sum()
        total_gastos_sin_factura = df_gn_filt.loc[~mask_con_factura, 'Monto'].sum()
    else:
        total_gastos_con_factura = 0.0
        total_gastos_sin_factura = 0.0

    # CÁLCULO DE IVA POR FLUJO DE EFECTIVO (NUEVO REQUERIMIENTO)
    total_efectivo_cobrado = df_an_filt['monto_abono'].sum() if not df_an_filt.empty else 0.0
    iva_flujo = (total_efectivo_cobrado / 1.16) * 0.16 if total_efectivo_cobrado > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💳 Flujo Cobrado (Abonos)", f"${total_efectivo_cobrado:,.2f}", 
              help="Dinero real nuevo depositado este mes.")
              
    c2.metric("🔴 IVA Causado SAT", f"${iva_flujo:,.2f}", 
              help="[EXTRACCION LEGAL]: El SAT exige el IVA solo de los depósitos bancarios reales. Esta fórmula extrae el 16% de todos los Abonos cobrados en esta ventana.")
              
    c3.metric("📉 OPEX (Con Factura)", f"-${total_gastos_con_factura:,.2f}", 
              help="Gastos deducibles que cuentan con comprobante XML/PDF.")
              
    c4.metric("📉 OPEX (Sin Factura)", f"-${total_gastos_sin_factura:,.2f}", 
              help="Gastos internos o sin comprobante fiscal.")

    st.markdown("---")
    
    # =================================================================
    # EXPORTACIÓN EXCEL MAESTRO (LIMPIO)
    # =================================================================
    st.markdown("### Exportación de Transacciones (Solo Operativo)")
    st.markdown("Tabla saneada y limpia para uso del contador, excluida de data histórica de abril.")
    
    if not df_an_filt.empty:
        # Unir abonos con los detalles de la venta (Cliente y Producto)
        df_export = pd.merge(
            df_an_filt, 
            df_todas[['ID_Venta', 'Cliente', 'Producto']], 
            left_on='venta_id', 
            right_on='ID_Venta', 
            how='left'
        )
        
        # Preparar columnas
        df_export['Fecha'] = df_export['fecha_abono'].dt.strftime('%d-%b-%Y')
        df_export['IVA_a_Pagar'] = (df_export['monto_abono'] / 1.16) * 0.16
        
        columnas_finales = ["Fecha", "Cliente", "Producto", "monto_abono", "IVA_a_Pagar"]
        df_mostrar = df_export[columnas_finales].copy()
        
        # Renombrar para presentación
        df_mostrar.rename(columns={'monto_abono': 'Abono_Recibido'}, inplace=True)
        
        # Formato de moneda
        df_mostrar['Abono_Recibido'] = df_mostrar['Abono_Recibido'].map("${:,.2f}".format)
        df_mostrar['IVA_a_Pagar'] = df_mostrar['IVA_a_Pagar'].map("${:,.2f}".format)
        
        st.dataframe(df_mostrar, width="stretch", height=500)
    else:
        st.caption("Aún no hay abonos descargables en la franja operativa actual.")
        
    st.markdown("---")
    
    # =================================================================
    # DESCARGA DE FACTURAS (XML / PDF)
    # =================================================================
    st.markdown("### 📥 Descarga de Facturas de Gastos")
    st.markdown("Facturas adjuntas a los gastos operativos en el periodo seleccionado.")
    
    if not df_gn_filt.empty:
        df_facturas = df_gn_filt[df_gn_filt['Tiene_Factura'] == True]
        if not df_facturas.empty:
            st.info(f"Se encontraron {len(df_facturas)} gastos con factura.")
            
            # Botón de Descarga Masiva (ZIP)
            import zipfile
            import io
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for _, row in df_facturas.iterrows():
                    prefix = f"gasto_{row['ID']}_{str(row['Fecha']).replace(':', '').replace(' ', '_').replace('-', '')}"
                    if row['Tiene_XML'] and row['XML_Bytes']:
                        zip_file.writestr(f"{prefix}.xml", row['XML_Bytes'])
                    if row['Tiene_PDF'] and row['PDF_Bytes']:
                        zip_file.writestr(f"{prefix}.pdf", row['PDF_Bytes'])
            
            st.download_button(
                label="📦 Descargar Todas las Facturas (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"Facturas_Gastos_Periodo.zip",
                mime="application/zip",
                type="primary"
            )
            
            st.markdown("#### Descarga Individual")
            for _, row in df_facturas.iterrows():
                with st.expander(f"Gasto #{row['ID']} - {row['Concepto']} (${row['Monto']:,.2f})"):
                    cols = st.columns(2)
                    if row['Tiene_XML'] and row['XML_Bytes']:
                        cols[0].download_button("📄 Descargar XML", data=row['XML_Bytes'], file_name=f"gasto_{row['ID']}.xml", mime="application/xml", key=f"xml_{row['ID']}")
                    if row['Tiene_PDF'] and row['PDF_Bytes']:
                        cols[1].download_button("📄 Descargar PDF", data=row['PDF_Bytes'], file_name=f"gasto_{row['ID']}.pdf", mime="application/pdf", key=f"pdf_{row['ID']}")
        else:
            st.caption("No hay gastos con factura (XML/PDF) en este periodo.")
    else:
        st.caption("No hay gastos registrados en este periodo.")
