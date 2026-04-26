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
    
    if st.button("Cerrar Pop-up", width="stretch"):
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
        # Cargar inventario real del vendedor
        df_inventario = db.leer_inventario(vendedor_email=st.session_state.user_email)
        
        with st.expander("📑 Ver mi Lista de Precios e Inventario", expanded=False):
            if not df_inventario.empty:
                df_mostrar = df_inventario[df_inventario['stock'].astype(int) > 0].copy()
                
                try:
                    from st_keyup import st_keyup
                    b_inv = st_keyup("🔍 Buscar en inventario", placeholder="Escribe parte del nombre...", key="busq_inv_keyup")
                except ImportError:
                    b_inv = st.text_input("🔍 Buscar en inventario", placeholder="Escribe parte del nombre... (Presiona Enter para buscar)")
                    
                if b_inv:
                    busq_txt = str(b_inv).lower()
                    df_mostrar = df_mostrar[df_mostrar["nombre"].astype(str).str.lower().str.contains(busq_txt)]
                
                if not df_mostrar.empty:
                    html_cards = ""
                    for _, row in df_mostrar.iterrows():
                        html_cards += f"""
                        <div style="background-color: #f8fafc; padding: 10px; border-radius: 6px; border-left: 4px solid #3b82f6; margin-bottom: 8px; font-size: 14px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                            <div style="font-weight: bold; color: #1e293b; margin-bottom: 4px;">🏷️ {row['nombre']}</div>
                            <div style="display: flex; justify-content: space-between; color: #475569;">
                                <div>📦 Stock Disp: <b style="color: #4338ca;">{int(row['stock'])}</b></div>
                                <div>💵 Precio Unitario: <b style="color: #059669;">${float(row['precio']):,.2f}</b></div>
                            </div>
                        </div>
                        """
                    st.markdown(html_cards, unsafe_allow_html=True)
                else:
                    st.info("Aún no tienes productos asignados a tu almacén.")
            else:
                st.info("Aún no tienes productos asignados a tu almacén.")
                
        st.subheader("🛒 Registro de Nueva Venta")
        
        opciones_inventario = []
        precio_dict = {}
        stock_dict = {}
        costo_ok_dict = {}
        
        if not df_inventario.empty:
            for _, row in df_inventario.iterrows():
                if int(row['stock']) > 0:
                    nombre = row['nombre']
                    cost_val = float(row.get('costo_compra', 0.0))
                    
                    if nombre not in opciones_inventario:
                        opciones_inventario.append(nombre)
                        precio_dict[nombre] = float(row['precio'])
                        stock_dict[nombre] = int(row['stock'])
                        costo_ok_dict[nombre] = (cost_val > 0)
                    else:
                        stock_dict[nombre] += int(row['stock'])
                        if cost_val > 0:
                            costo_ok_dict[nombre] = True
                        
        if not opciones_inventario:
            st.warning("⚠️ No cuentas con inventario. Solicita al administrador que te asigne stock para poder registrar ventas.")
        else:
            producto = st.selectbox(
                "Selecciona el producto a vender del inventario", 
                opciones_inventario,
                index=None,
                placeholder="Elige un producto de la lista..."
            )
            
            if producto and producto in stock_dict:
                 st.info(f"📦 Stock disponible en tu almacén: **{stock_dict[producto]}** unidades.")
                 limite_cantidad = stock_dict[producto]
                 precio_def = precio_dict[producto]
            else:
                 limite_cantidad = 1000
                 precio_def = 0.0
            
            with st.form("venta_form", clear_on_submit=False):
                st.markdown("### 📝 Datos de Venta")
                cliente = st.text_input("👤 Nombre Completo del Cliente", placeholder="Ej: Maria Lopez")
                
                # Usar Selectbox en vez de NumberInput para la cantidad (Es más fácil en el celular)
                opciones_cantidad = list(range(1, min(51, limite_cantidad + 1)))
                cantidad = st.selectbox("📦 Cantidad a vender", opciones_cantidad)
                
                precio = st.number_input("💵 Precio Unitario Final ($)", min_value=0.0, step=50.0, format="%.2f", value=precio_def, key=f"precio_venta_input")
                
                st.markdown("<br>", unsafe_allow_html=True)
                tipo_v = st.session_state.get("user_tipo_vendedor", "Crédito")
                if tipo_v == "One-Shot":
                    # Forzar cobro total
                    st.info("🎟️ Tu perfil está etiquetado como Vendedor One-Shot. Esta venta se registrará automáticamente como liquidada 100% al contado.")
                    pagado_check = True
                else:
                    pagado_check = False
                                
                # Botón de envio
                submit_venta = st.form_submit_button("Registrar Venta")
                
                if submit_venta:
                    if not cliente:
                        st.error("El nombre del cliente es obligatorio.")
                    elif not producto:
                        st.error("Por favor selecciona un producto.")
                    elif producto in costo_ok_dict and not costo_ok_dict[producto]:
                        # Bloqueamos productos incompletos (sin costo_compra)
                        st.error("❌ Este producto no fue cargado correctamente en el sistema (Falta información de inventario previa). Por favor pide al administrador que lo asigne antes de venderlo.")
                    else:
                        prod_final = producto
                        
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
                st.write("Ventas liquidadas listas para cobrar tu comisión:")
                
                for idx, row in df_por_cobrar.iterrows():
                    st.markdown(f"""
                    <div style="border-left: 6px solid #3b82f6; background-color: rgba(59, 130, 246, 0.08); padding: 12px; border-radius: 6px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                        <div style="font-size: 16px; font-weight: bold; margin-bottom: 6px; color: #1f2937;">👤 Cliente: {row['Cliente']}</div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #374151;">📦 <b>Perfume:</b> {row['Producto']}</div>
                        <div style="font-size: 14px; margin-bottom: 4px; color: #374151;">💵 <b>Costo Venta Total:</b> ${row['Total_Venta']:,.2f}</div>
                        <div style="font-size: 15px; color: #2563eb; font-weight: bold; margin-top: 6px;">💰 <b>Tu Comisión:</b> ${row['Comision_Generada']:,.2f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Usamos un expander para esconder y mostrar la confirmación (hace el efecto de un botón que pide confirmación)
                    with st.expander(f"📥 Retirar Comisión de {row['Cliente']}"):
                        st.warning(f"¿Estás seguro de registrar y marcar como retirados estos **${row['Comision_Generada']:,.2f}**?")
                        if st.button("✅ Sí, Confirmar Retiro", key=f"btn_cobrar_{row['ID_Venta']}", width="stretch"):
                            exito_cobro, msj_cobro = db.marcar_comision_cobrada(row['ID_Venta'])
                            if exito_cobro:
                                st.success("Comisión retirada exitosamente.")
                                st.rerun()
                            else:
                                st.error(msj_cobro)
                    st.markdown("<br>", unsafe_allow_html=True)
            else:
                st.info("No tienes comisiones liberadas pendientes de retirar.")
        else:
            st.info("Aún no tienes ventas registradas.")

    with col2:
        st.subheader("💰 Mis Métricas Desglosadas")
        
        df_todas = db.obtener_tabla_ventas_completa()
        df_abonos = db.leer_abonos()
        
        # === MÉTRICAS GLOBALES (Siempre visibles) ===
        st.markdown("##### 🌎 Panorama Global")
        
        comisiones_pendientes_global = 0.0
        comisiones_listas_global = 0.0
        ventas_totales_global = 0.0
        cartera_total_global = 0.0
        
        if not df_todas.empty:
            df_mis_ventas = df_todas[df_todas["Nombre_Vendedor"] == st.session_state.user_name].copy()
            ventas_totales_global = df_mis_ventas["Total_Venta"].sum()
            
            df_pagadas = df_mis_ventas[df_mis_ventas["Estado_Venta"] == "Pagado"]
            comisiones_listas_global = df_pagadas[df_pagadas["Comision_Fisicamente_Cobrada"] == False]["Comision_Generada"].sum()
            
            df_adeudos_metric = df_mis_ventas[df_mis_ventas["Estado_Venta"] == "Adeudo"]
            comisiones_pendientes_global = df_adeudos_metric["Comision_Generada"].sum()
            cartera_total_global = pd.to_numeric(df_adeudos_metric["Saldo_Pendiente"], errors='coerce').sum()
            
            # Formatear fechas para operaciones
            df_mis_ventas["Fecha_Venta_DT"] = pd.to_datetime(df_mis_ventas["Fecha_Venta"], format="%d-%b-%Y", errors='coerce')
            df_mis_ventas["Fecha_Cobro_Comision_DT"] = pd.to_datetime(df_mis_ventas["Fecha_Cobro_Comision"], format="%d-%b-%Y", errors='coerce')
        else:
            df_mis_ventas = pd.DataFrame()
            
        # Usamos tarjetas HTML personalizadas para evitar los recortes nativos (...) de Streamlit
        st.markdown(f"""
        <div style="border-left: 5px solid #10b981; background-color: rgba(16, 185, 129, 0.08); padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="color: #047857; font-weight: bold; font-size: 15px; margin-bottom: 5px; line-height: 1.3;">🟢 Comisiones Listas para Retirar</div>
            <div style="color: #1f2937; font-size: 28px; font-weight: 900;">${comisiones_listas_global:,.2f} <span style="font-size:16px; color:#6b7280; font-weight:600;">MXN</span></div>
        </div>
        
        <div style="border-left: 5px solid #3b82f6; background-color: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="color: #1d4ed8; font-weight: bold; font-size: 15px; margin-bottom: 5px; line-height: 1.3;">🔵 Comisiones pendientes por retirar hasta que se finalice la venta</div>
            <div style="color: #1f2937; font-size: 28px; font-weight: 900;">${comisiones_pendientes_global:,.2f} <span style="font-size:16px; color:#6b7280; font-weight:600;">MXN</span></div>
        </div>
        
        <div style="border-left: 5px solid #ef4444; background-color: rgba(239, 68, 68, 0.08); padding: 15px; border-radius: 8px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="color: #b91c1c; font-weight: bold; font-size: 15px; margin-bottom: 5px; line-height: 1.3;">🔴 Cartera Total (Dinero Pendiente a Cobrar)</div>
            <div style="color: #1f2937; font-size: 28px; font-weight: 900;">${cartera_total_global:,.2f} <span style="font-size:16px; color:#6b7280; font-weight:600;">MXN</span></div>
        </div>
        
        <div style="border-left: 5px solid #f59e0b; background-color: rgba(245, 158, 11, 0.08); padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="color: #b45309; font-weight: bold; font-size: 15px; margin-bottom: 5px; line-height: 1.3;">🏆 Ventas Históricas Totales</div>
            <div style="color: #1f2937; font-size: 28px; font-weight: 900;">${ventas_totales_global:,.2f} <span style="font-size:16px; color:#6b7280; font-weight:600;">MXN</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("##### 📅 Rendimiento por Mes")
        
        # --- LÓGICA DE 5 MESES ANTERIORES ---
        meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        # Calcular los ultimos 5 meses de forma robusta
        hoy = datetime.datetime.now()
        ultimos_meses_str = []
        periodos = []
        
        for i in range(5):
            mes_calculado = hoy.month - i
            año_calculado = hoy.year
            if mes_calculado <= 0:
                mes_calculado += 12
                año_calculado -= 1
                
            nombre_mes = f"{meses_nombres[mes_calculado - 1]} {año_calculado}"
            if i == 0:
                nombre_mes = f"🗓️ {meses_nombres[mes_calculado - 1]} (Actual)"
            else:
                nombre_mes = f"🗓️ {meses_nombres[mes_calculado - 1]}"
                
            ultimos_meses_str.append(nombre_mes)
            periodos.append((año_calculado, mes_calculado))

        # Crear los tabs de Streamlit
        tabs = st.tabs(ultimos_meses_str)
        
        for index, tab in enumerate(tabs):
            with tab:
                año_m, mes_m = periodos[index]
                
                # Calcular datos específicos para este mes
                ventas_mes_val = 0.0
                ventas_cerradas_val = 0.0
                abonos_mes_val = 0.0
                comisiones_recibidas_val = 0.0
                
                if not df_mis_ventas.empty:
                    # 1. Ventas Totales iniciadas en este mes
                    df_mes = df_mis_ventas[(df_mis_ventas["Fecha_Venta_DT"].dt.year == año_m) & (df_mis_ventas["Fecha_Venta_DT"].dt.month == mes_m)]
                    ventas_mes_val = df_mes["Total_Venta"].sum()
                    
                    # 2. Ventas Cerradas del mes (Pagadas completamente independientemente de cuando se iniciaron)
                    # wait: The prompt asked for "ventas cerradas del mes". This usually means Sales originating in that month that are entirely paid, OR Sales that reached paid status in that month. Usually it means the former if we calculate "Ventas" metrics.
                    ventas_cerradas_val = df_mes[df_mes["Estado_Venta"] == "Pagado"]["Total_Venta"].sum()
                    
                    # 4. Comisiones retiradas físimacamente en este mes
                    df_cobros_mes = df_mis_ventas[(df_mis_ventas["Fecha_Cobro_Comision_DT"].dt.year == año_m) & (df_mis_ventas["Fecha_Cobro_Comision_DT"].dt.month == mes_m)]
                    comisiones_recibidas_val = df_cobros_mes["Comision_Generada"].sum()
                
                # 3. Abonos del mes
                if not df_abonos.empty and not df_mis_ventas.empty:
                    # Filtrar solo abonos de las ventas DE ESTE vendedor
                    mis_ventas_ids = df_mis_ventas["ID_Venta"].tolist()
                    df_abonos_mios = df_abonos[df_abonos["venta_id"].isin(mis_ventas_ids)].copy()
                    
                    if not df_abonos_mios.empty:
                        df_abonos_mios["fecha_dt"] = pd.to_datetime(df_abonos_mios["fecha_abono"], errors='coerce')
                        abonos_mes = df_abonos_mios[(df_abonos_mios["fecha_dt"].dt.year == año_m) & (df_abonos_mios["fecha_dt"].dt.month == mes_m)]
                        abonos_mes_val = abonos_mes["monto_abono"].sum()
                        
                # Dibujar UI de métricas del mes seleccionado usando Grid CSS para encajar perfecto en móvil
                st.markdown(f"**Resumen de {meses_nombres[mes_m-1]} {año_m}**")
                
                st.markdown(f"""
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 15px;">
                    <div style="background-color: #f3f4f6; padding: 12px; border-radius: 8px; border-bottom: 3px solid #9ca3af;">
                        <div style="font-size: 13px; color: #4b5563; font-weight: 700; margin-bottom: 4px; line-height: 1.2;">🛒 Ventas Totales</div>
                        <div style="font-size: 21px; font-weight: 900; color: #111827;">${ventas_mes_val:,.2f}</div>
                    </div>
                    <div style="background-color: #f3f4f6; padding: 12px; border-radius: 8px; border-bottom: 3px solid #3b82f6;">
                        <div style="font-size: 13px; color: #4b5563; font-weight: 700; margin-bottom: 4px; line-height: 1.2;">💸 Abonos Recibidos</div>
                        <div style="font-size: 21px; font-weight: 900; color: #1d4ed8;">${abonos_mes_val:,.2f}</div>
                    </div>
                    <div style="background-color: #f3f4f6; padding: 12px; border-radius: 8px; border-bottom: 3px solid #10b981;">
                        <div style="font-size: 13px; color: #4b5563; font-weight: 700; margin-bottom: 4px; line-height: 1.2;">📦 Ventas 100% Cerradas</div>
                        <div style="font-size: 21px; font-weight: 900; color: #047857;">${ventas_cerradas_val:,.2f}</div>
                    </div>
                    <div style="background-color: #f3f4f6; padding: 12px; border-radius: 8px; border-bottom: 3px solid #f59e0b;">
                        <div style="font-size: 13px; color: #4b5563; font-weight: 700; margin-bottom: 4px; line-height: 1.2;">💰 Comisiones Retiradas</div>
                        <div style="font-size: 21px; font-weight: 900; color: #b45309;">${comisiones_recibidas_val:,.2f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                    
        st.markdown("---")
        
        st.subheader("⚠️ Clientes con Adeudo")
        
        if not df_todas.empty:
            # Traemos más columnas para el popup (Fecha_Venta, Total_Venta, ID_Venta)
            df_adeudos = df_mis_ventas[df_mis_ventas["Estado_Venta"] == "Adeudo"][["ID_Venta", "Fecha_Venta", "Cliente", "Producto", "Total_Venta", "Saldo_Pendiente", "Dias_Ultimo_Abono", "Total_Abono"]].copy()
            
            if not df_adeudos.empty:
                try:
                    from st_keyup import st_keyup
                    b_adeudo = st_keyup("🔍 Buscar Cliente o Producto", placeholder="Escribe para buscar en tus cuentas por cobrar...", key="busq_adeudos_keyup")
                except ImportError:
                    b_adeudo = st.text_input("🔍 Buscar Cliente o Producto", placeholder="Escribe para buscar en tus cuentas por cobrar... (Presiona Enter)")
                
                if b_adeudo:
                    str_b = str(b_adeudo).lower()
                    df_adeudos = df_adeudos[
                        df_adeudos["Cliente"].astype(str).str.lower().str.contains(str_b) |
                        df_adeudos["Producto"].astype(str).str.lower().str.contains(str_b)
                    ]
                    if df_adeudos.empty:
                        st.info("Sin resultados para esta búsqueda.")
                
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

    # --- SECCIÓN: GANANCIAS DE RED (MULTI-NIVEL) ---
    st.markdown("---")
    st.subheader("🌐 Portal de Liderazgo (Red MLM 3 Niveles)")
    st.markdown("Aquí se reflejan las ganancias generadas automáticamente por las ventas **cerradas y liquidadas al 100%** de toda tu red descendente jerárquica.")
    
    df_red, niveles_dict, bono_total_red, miembros_red = db.leer_metricas_red(st.session_state.user_email)
    
    if bono_total_red > 0 or miembros_red:
        st.markdown(f'''
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 style="margin: 0; font-size: 18px; font-weight: 500;">Acumulado Global a Cobrar (3 Niveles)</h3>
            <h1 style="margin: 5px 0 0 0; font-size: 36px; font-weight: 800;">${bono_total_red:,.2f} MXN</h1>
        </div>
        ''', unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Nivel 1 (5%)", f"${niveles_dict[1]['bono']:,.2f}")
        c2.metric("Nivel 2 (3%)", f"${niveles_dict[2]['bono']:,.2f}")
        c3.metric("Nivel 3 (2%)", f"${niveles_dict[3]['bono']:,.2f}")
        
        st.markdown("---")
        st.markdown("### 👁️ Rayos X: Cartera de tu Red")
        st.markdown("Revisa el desempeño exacto y audita las deudas pendientes de tus afiliados.")
        
        opciones_miembros = ["Seleccionar miembro..."] + [f"{m['Nombre']} (Nivel {m['Nivel']} - {int(m['Tasa_Paga']*100)}%) | {m['Email']}" for m in miembros_red]
        miembro_seleccionado_str = st.selectbox("Selecciona un vendedor de tu equipo para inspeccionar:", opciones_miembros)
        
        if miembro_seleccionado_str != "Seleccionar miembro...":
            # Extraer email y nombre
            email_target = miembro_seleccionado_str.split(" | ")[1]
            nombre_target = miembro_seleccionado_str.split(" (Nivel")[0]
            
            st.markdown(f"#### 🔎 Inspeccionando a: **{nombre_target}**")
            
            # Obtener datos de este miembro (reutlizando el dataframe global)
            df_update = db.obtener_tabla_ventas_completa()
            if not df_update.empty:
                df_target = df_update[df_update["Nombre_Vendedor"] == nombre_target]
                
                if df_target.empty:
                    st.info(f"{nombre_target} aún no tiene ventas registradas en el sistema.")
                else:
                    df_target_adeudos = df_target[df_target["Estado_Venta"] == "Adeudo"][["ID_Venta", "Fecha_Venta", "Cliente", "Producto", "Total_Venta", "Saldo_Pendiente", "Dias_Ultimo_Abono", "Total_Abono"]].copy()
                    
                    st.markdown("##### 🚨 Clientes que le deben dinero (Vista de Sólo Lectura)")
                    if not df_target_adeudos.empty:
                        df_target_adeudos = df_target_adeudos.sort_values(by="Dias_Ultimo_Abono", ascending=False)
                        for _, row in df_target_adeudos.iterrows():
                            dias = int(row["Dias_Ultimo_Abono"]) if pd.notna(row["Dias_Ultimo_Abono"]) else 0
                            borde = "#ff4b4b" if dias > 30 else ("#ffcc00" if dias >= 20 else "#28a745")
                            fondo = "rgba(255, 75, 75, 0.1)" if dias > 30 else ("rgba(255, 204, 0, 0.15)" if dias >= 20 else "rgba(40, 167, 69, 0.1)")
                            
                            st.markdown(f"""
                            <div style="border-left: 6px solid {borde}; background-color: {fondo}; padding: 12px; border-radius: 6px; margin-bottom: 12px;">
                                <div style="font-size: 16px; font-weight: bold; margin-bottom: 6px; color: #1f2937;">👤 {row['Cliente']}</div>
                                <div style="font-size: 14px; margin-bottom: 4px;">📦 <b>Producto:</b> {row['Producto']}</div>
                                <div style="font-size: 14px; margin-bottom: 4px;">💵 <b>Saldo Pendiente:</b> <span style="font-weight: bold;">${float(row['Saldo_Pendiente']):,.2f}</span></div>
                                <div style="font-size: 14px;">⏳ <b>Sin abonos hace:</b> {dias} días</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Mostrar un expansor nativo con el resumen en vez de usar el pop-up editable
                            with st.expander(f"Ver pagos de {row['Cliente']}"):
                                st.write(f"**Costo Total Original:** ${float(row['Total_Venta']):,.2f}")
                                st.write(f"**Total Abonado Hasta Ahora:** ${float(row['Total_Abono']):,.2f}")
                                st.info("🔒 Como líder puedes auditar, pero la cobranza y captura de abonos físicos es responsabilidad administrativa.")
                    else:
                        st.success(f"¡Excelente! {nombre_target} no tiene clientes con deudas vigentes.")
                        
                    st.divider()
                    st.markdown("##### 💵 Ventas finalizadas (Generadoras de Regalías)")
                    if not df_red.empty:
                        df_target_red = df_red[df_red["Vendedor"] == nombre_target]
                        if not df_target_red.empty:
                            for _, row in df_target_red.iterrows():
                                st.markdown(f'''
                                <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid #10b981; margin-bottom: 10px;">
                                    <div style="font-weight:bold; font-size:16px;">Venta a: {row['Cliente']} <span style="float:right; font-size:13px; font-weight:normal; color:#64748b;">🗓️ {row['Fecha']}</span></div>
                                    <div style="color: #475569; font-size: 14px; margin-bottom: 4px;">Monto Cerrado: ${row['Total_Venta']:,.2f}</div>
                                    <div style="color: #047857; font-size: 16px; font-weight:bold; margin-bottom: 0px;">Tu Bono de Red ({row['Porcentaje']}): +${row['Bono_Ganado']:,.2f}</div>
                                </div>
                                ''', unsafe_allow_html=True)
                        else:
                            st.write("Aún no ha cerrado deudas completas que generen comisión activa.")
                    
    else:
        st.info("Actualmente no tienes vendedores adscritos o en vigencia estructural.")
