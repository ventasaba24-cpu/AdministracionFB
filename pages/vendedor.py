import streamlit as st
import pandas as pd
import datetime

# Habilitar diálogos de Streamlit (Pop-up)
if hasattr(st, "dialog"):
    dialog_decorator = st.dialog
elif hasattr(st, "experimental_dialog"):
    dialog_decorator = st.experimental_dialog
else:
    # Fallback por si la version de Streamlit es muy vieja, aunque no debería
    def dialog_decorator(title):
        def decorator(func):
            return func
        return decorator

@dialog_decorator("ℹ️ Detalles Completos del Cliente")
def mostrar_detalles_popup(row):
    st.markdown(f"**Usuario / Cliente:** {row['Cliente']}")
    st.markdown(f"**Fecha de Compra:** {row['Fecha_Venta']}")
    st.markdown(f"**Producto Adquirido:** {row['Producto']}")
    st.markdown("---")
    # Nota: Mostramos Total_Venta en lugar de Costo_Producto para proteger la visibilidad del costo (COGS) según reglas del admin.
    st.markdown(f"**Precio Real de Venta (Lo que costó al cliente):** :green[${float(row['Total_Venta']):,.2f}]")
    st.markdown(f"**Abonos Totales (Acumulado):** :blue[${float(row['Total_Abono']):,.2f}]")
    
    # 🔍 Extraer historial de abonos individuales para esta venta
    from database import DatabaseHandler
    import pandas as pd
    db = DatabaseHandler()
    df_abonos = db.leer_abonos()
    
    # Filtrar solo los abonos que pertenecen a esta Venta y ordenarlos por fecha
    abonos_venta = df_abonos[df_abonos['venta_id'] == row['ID_Venta']].sort_values(by="fecha_abono")
    
    if not abonos_venta.empty:
        st.markdown("<br>**🧾 Historial Individual de Abonos:**", unsafe_allow_html=True)
        for estado_i, (idx, abono) in enumerate(abonos_venta.iterrows(), start=1):
            fecha = abono['fecha_abono']
            if pd.notna(fecha):
                fecha_str = pd.to_datetime(fecha).strftime("%d/%b/%Y")
            else:
                fecha_str = "Fecha Desconocida"
                
            monto = float(abono['monto_abono'])
            metodo = abono.get('metodo_pago', 'Efectivo')
            st.markdown(f"👉 **Abono {estado_i}:** {fecha_str} | **${monto:,.2f}** *({metodo})*")
    else:
         st.markdown("<br>*(Este cliente aún no tiene registros de abonos individuales)*", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"**Adeudo Actual Pendiente:** :red[${float(row['Saldo_Pendiente']):,.2f}]")
    
    if st.button("Cerrar Pop-up", use_container_width=True):
        st.rerun()

# Función principal a llamar desde app.py
def show():
    st.title("👨💼 Panel de Vendedor")
    st.markdown("---")
    
    # Importación perezosa
    from database import DatabaseHandler
    db = DatabaseHandler()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🛒 Registro de Nueva Venta")
        
        # Cargar inventario real del vendedor
        df_inventario = db.leer_inventario(vendedor_email=st.session_state.user_email)
        opciones_inventario = []
        precio_dict = {}
        stock_dict = {}
        
        if not df_inventario.empty:
            for _, row in df_inventario.iterrows():
                if int(row['stock']) > 0:
                    nombre = row['nombre']
                    opciones_inventario.append(nombre)
                    precio_dict[nombre] = float(row['precio'])
                    stock_dict[nombre] = int(row['stock'])
                    
        opciones_inventario.append("Otro (Especificar producto fuera de listado)")
        
        producto = st.selectbox("🛒 Producto a Vender", opciones_inventario)
        
        if producto in stock_dict:
             st.info(f"📦 Stock disponible en tu almacén: **{stock_dict[producto]}** unidades.")
             limite_cantidad = stock_dict[producto]
             precio_def = precio_dict[producto]
        else:
             limite_cantidad = 1000
             precio_def = 0.0
        
        with st.form("venta_form"):
            if producto == "Otro (Especificar producto fuera de listado)":
                producto_custom = st.text_input("Nombre específico (requerido si marcaste 'Otro')")
            else:
                producto_custom = ""
            
            cliente = st.text_input("Nombre del Cliente")
            cantidad = st.number_input("Cantidad a vender", min_value=1, max_value=limite_cantidad, value=1)
            precio = st.number_input("Precio Unitario Final ($)", min_value=0.0, step=10.0, format="%.2f", value=precio_def, key=f"precio_{producto}")
            
            pagado_check = st.checkbox("¿Cobro total inmediato (Al contado)?")
            
            # Botón de envio
            submit_venta = st.form_submit_button("Registrar Venta")
            
            if submit_venta:
                if not cliente:
                    st.error("El nombre del cliente es obligatorio.")
                elif producto == "Otro (Especificar producto fuera de listado)" and not producto_custom:
                    st.error("Debes especificar el nombre del producto nuevo.")
                else:
                    prod_final = producto_custom if producto_custom else producto
                    
                    st.toast(f"Procesando venta de {prod_final}...")
                    
                    # Llamada a DB 
                    exito, id_v, monto = db.registrar_venta(st.session_state.user_email, cliente, prod_final, cantidad, precio)
                    
                    if exito:
                        st.success(f"Venta #{id_v} registrada exitosamente para el cliente {cliente} por ${monto:,.2f} MXN.")
                        if pagado_check:
                             # Auto-registrar abono completo instantáneo
                             db.registrar_abono(id_v, monto, "Efectivo")
                             st.info(f"Comisión registrada: ${(monto * st.session_state.user_comision):,.2f} MXN")
                    else:
                        st.error("Error al registrar en la base de datos.")

        # --- SECCIÓN: COBRO DE COMISIONES ---
        st.markdown("---")
        st.subheader("💳 Retiro de Comisiones")
        
        # Obtenemos datos recientes
        df_update = db.obtener_tabla_ventas_completa()
        if not df_update.empty:
            df_mis = df_update[df_update["Nombre_Vendedor"] == st.session_state.user_name]
            # Filtrar las ventas que ESTAN pagadas pero NO se han cobrado su comision
            df_por_cobrar = df_mis[(df_mis["Estado_Venta"] == "Pagado") & (df_mis["Comision_Fisicamente_Cobrada"] == False)]
            
            if not df_por_cobrar.empty:
                st.write("Selecciona una venta liquidadada para informarle al sistema que ya recibiste tu comisión monetaria.")
                
                # Crear diccionario para opciones descriptivas legibles
                opciones = {}
                for idx, row in df_por_cobrar.iterrows():
                    desc = f"Venta #{row['ID_Venta']} | {row['Producto']} | Cliente: {row['Cliente']} | Comisión: ${row['Comision_Generada']:,.2f}"
                    opciones[row['ID_Venta']] = desc
                    
                with st.form("form_cobrar_comision"):
                    venta_seleccionada = st.selectbox(
                        "Comisiones disponibles", 
                        options=list(opciones.keys()),
                        format_func=lambda x: opciones[x]
                    )
                    btn_cobrar = st.form_submit_button("Confirmar recepción de esta comisión")
                    
                    if btn_cobrar:
                        exito_cobro, msj_cobro = db.marcar_comision_cobrada(venta_seleccionada)
                        if exito_cobro:
                            st.success(msj_cobro)
                            st.rerun()
                        else:
                            st.error(msj_cobro)
            else:
                st.info("No tienes comisiones liberadas pendientes de retirar.")
        else:
            st.info("Aún no tienes ventas registradas.")

    with col2:
        st.subheader("💰 Mis Métricas (Mes Actual)")
        
        # Leer todas las ventas y filtrar
        df_todas = db.obtener_tabla_ventas_completa()
        
        if not df_todas.empty:
            df_mis_ventas = df_todas[df_todas["Nombre_Vendedor"] == st.session_state.user_name]
            
            ventas_mes = df_mis_ventas["Total_Venta"].sum()
            
            # Comisiones de ventas pagadas (Aprobadas para cobro)
            df_pagadas = df_mis_ventas[df_mis_ventas["Estado_Venta"] == "Pagado"]
            
            # Filtrar las que ya cobró físicamente vs las que están listas
            comisiones_ya_cobradas = df_pagadas[df_pagadas["Comision_Fisicamente_Cobrada"] == True]["Comision_Generada"].sum()
            comisiones_listas = df_pagadas[df_pagadas["Comision_Fisicamente_Cobrada"] == False]["Comision_Generada"].sum()
            
            # Comisiones pendientes de ventas con adeudo
            df_adeudos_metric = df_mis_ventas[df_mis_ventas["Estado_Venta"] == "Adeudo"]
            comisiones_pendientes = df_adeudos_metric["Comision_Generada"].sum()
        else:
            ventas_mes = 0.0
            comisiones_ya_cobradas = 0.0
            comisiones_listas = 0.0
            comisiones_pendientes = 0.0
        
        st.metric(label="Ventas del Mes", value=f"${ventas_mes:,.2f} MXN")
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric(label="💰 Comisiones en Bolsillo", value=f"${comisiones_ya_cobradas:,.2f} MXN", delta="Ya Cobradas")
        with col_m2:
            st.metric(label="🟢 Listas para Retirar", value=f"${comisiones_listas:,.2f} MXN", delta="Disponibles", delta_color="normal")
            
        st.metric(label="Comisiones Pendientes", value=f"${comisiones_pendientes:,.2f} MXN", delta="Se pagan al liquidar adeudo", delta_color="off")
        
        st.markdown("---")
        
        st.subheader("⚠️ Clientes con Adeudo")
        
        if not df_todas.empty:
            # Traemos más columnas para el popup (Fecha_Venta, Total_Venta, ID_Venta)
            df_adeudos = df_mis_ventas[df_mis_ventas["Estado_Venta"] == "Adeudo"][["ID_Venta", "Fecha_Venta", "Cliente", "Producto", "Total_Venta", "Saldo_Pendiente", "Dias_Ultimo_Abono", "Total_Abono"]].copy()
            
            if not df_adeudos.empty:
                df_adeudos = df_adeudos.sort_values(by="Dias_Ultimo_Abono", ascending=False)
                
                # Mostrar como "Tarjetas" (Cards) HTML para una vista perfecta en celulares
                for _, row in df_adeudos.iterrows():
                    dias = row["Dias_Ultimo_Abono"]
                    try:
                        dias = int(dias)
                    except:
                        dias = 0
                        
                    if dias > 30:
                        borde = "#ff4b4b" # Rojo
                        fondo = "rgba(255, 75, 75, 0.1)"
                    elif dias >= 20: 
                        borde = "#ffcc00" # Amarillo
                        fondo = "rgba(255, 204, 0, 0.15)"
                    else:
                        borde = "#28a745" # Verde
                        fondo = "rgba(40, 167, 69, 0.1)"
                        
                    saldo = f"${float(row['Saldo_Pendiente']):,.2f}"
                    
                    # Dibujar Tarjeta
                    st.markdown(f"""
                    <div style="border-left: 6px solid {borde}; background-color: {fondo}; padding: 12px; border-radius: 6px; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <div style="font-size: 16px; font-weight: bold; margin-bottom: 6px; color: #1f2937;">👤 {row['Cliente']}</div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #374151;">📦 <b>Producto:</b> {row['Producto']}</div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #374151;">💵 <b>Saldo Pendiente:</b> <span style="color: {borde if borde != '#ffcc00' else '#d97706'}; font-weight: bold;">{saldo}</span></div>
                        <div style="font-size: 14px; color: #374151;">⏳ <b>Sin abonos hace:</b> {dias} días</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"🔍 Ver detalles de {row['Cliente']}", key=f"btn_det_{row['ID_Venta']}"):
                        mostrar_detalles_popup(row)
            else:
                st.success("¡Excelente! No tienes ningún cliente con deudas.")
        else:
            st.info("No hay ventas registradas.")
