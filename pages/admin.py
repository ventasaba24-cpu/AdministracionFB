import streamlit as st
import pandas as pd

@st.dialog("Edición Completa de Venta")
def dialog_editar_venta(venta_info, df_inventario, db):
    st.markdown("⚠️ **Cambiarás los detalles de esta venta. El inventario se ajustará automáticamente.**")
    
    nuevo_cliente = st.text_input("Nombre de Cliente", value=venta_info['Cliente'])
    nuevo_monto = st.number_input("Precio Cobrado ($)", min_value=0.0, value=float(venta_info['Total_Venta']), step=50.0)
    
    # Preparar opciones de productos
    opciones_prod = df_inventario["nombre"].tolist() if not df_inventario.empty else [venta_info['Producto']]
    if venta_info['Producto'] not in opciones_prod:
        opciones_prod.append(venta_info['Producto'])
        
    index_prod = opciones_prod.index(venta_info['Producto'])
    nuevo_producto = st.selectbox("Producto Entregado", options=opciones_prod, index=index_prod)
    
    nueva_cantidad = st.number_input("Cantidad de Piezas", min_value=1, value=int(venta_info.get('cantidad', 1)), step=1)
    
    if st.button("💾 Guardar Corrección", type="primary", use_container_width=True):
        exito, msj = db.editar_venta_completa(venta_info['ID_Venta'], nuevo_cliente, nuevo_producto, nueva_cantidad, nuevo_monto)
        if exito:
            st.success(msj)
            st.rerun()
        else:
            st.error(msj)

@st.dialog("Edición de Abono")
def dialog_editar_abono(abono_info, db):
    st.markdown("Modifica el recibo de este pago.")
    nuevo_monto = st.number_input("Monto Abonado ($)", min_value=0.0, value=float(abono_info['monto_abono']), step=50.0)
    metodos = ["Efectivo", "Transferencia", "Tarjeta"]
    idx_m = metodos.index(abono_info['metodo_pago']) if abono_info['metodo_pago'] in metodos else 0
    nuevo_metodo = st.selectbox("Método de Pago", options=metodos, index=idx_m)
    
    if st.button("💾 Actualizar Recibo", type="primary", use_container_width=True):
        exito, msj = db.editar_abono(abono_info['id_abono'], nuevo_monto, nuevo_metodo)
        if exito:
            st.success(msj)
            st.rerun()
        else:
            st.error(msj)


def show():
    # Esta página requerirá rol Admin
    if st.session_state.user_role != "Admin":
        st.error("Acceso DENEGADO. Requiere privilegios de Administrador.")
        st.stop()
        
    st.title("🛡️ Panel de Control de Administración")
    
    # Importación perezosa
    from database import DatabaseHandler
    db = DatabaseHandler()

    # 📌 PRE-CARGAR DATOS PESADOS UNA SOLA VEZ PARA OPTIMIZAR VELOCIDAD
    df_todas = db.obtener_tabla_ventas_completa()
    df_abonos_global = db.leer_abonos()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 KPIs", "📦 Inventario", "💵 Abonos/Pagos", "✉️ Vendedores", "📝 Correcciones"])

    with tab1:
        st.subheader("Indicadores Clave de Desempeño")
        if not df_todas.empty:
            ventas_totales = df_todas["Total_Venta"].sum()
            utilidad_neta = df_todas["Utilidad_Neta"].sum()
            iva_generado = df_todas["IVA_(16%)"].sum()
            costo_total = df_todas["Costo_Producto"].sum()
            comisiones_totales = df_todas["Comision_Generada"].sum()
            
            producto_top = df_todas.groupby("Producto")["Total_Venta"].sum().idxmax() if not df_todas.empty else "N/A"
            vendedor_top = df_todas.groupby("Nombre_Vendedor")["Total_Venta"].sum().idxmax() if not df_todas.empty else "N/A"
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Ventas Totales Brutas", f"${ventas_totales:,.2f}")
            col2.metric("✨ Utilidad Neta (Libre)", f"${utilidad_neta:,.2f}", "Ganancia Real", delta_color="normal")
            col3.metric("IVA Reservado (16%)", f"${iva_generado:,.2f}")
            col4.metric("Costos y Comisiones", f"${costo_total + comisiones_totales:,.2f}")
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            c1.info(f"🏆 **Producto Estrella en Ventas:** {producto_top}")
            c2.success(f"🥇 **Mejor Vendedor(a):** {vendedor_top}")
            
            st.markdown("---")
            st.markdown("---")
            st.subheader("Desglose Financiero y Comisiones por Vendedor")
            df_com = df_todas.groupby("Nombre_Vendedor").agg({
                "Total_Venta": "sum",
                "Costo_Producto": "sum",
                "IVA_(16%)": "sum",
                "Comision_Generada": "sum",
                "Utilidad_Neta": "sum"
            }).reset_index()
            
            for _, r in df_com.iterrows():
                costo_iva = r['Costo_Producto'] + r['IVA_(16%)']
                st.markdown(f"""
                <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                    <div style="font-size: 16px; font-weight: bold; color: #1e293b; margin-bottom: 8px;">👤 {r['Nombre_Vendedor']}</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Ventas Totales</span><br><span style="font-size: 15px; font-weight: 800; color: #0f172a;">${r['Total_Venta']:,.2f}</span></div>
                        <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Utilidad Neta</span><br><span style="font-size: 15px; font-weight: 800; color: #10b981;">${r['Utilidad_Neta']:,.2f}</span></div>
                        <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Comisiones</span><br><span style="font-size: 15px; font-weight: 800; color: #f59e0b;">${r['Comision_Generada']:,.2f}</span></div>
                        <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Costo + IVA</span><br><span style="font-size: 15px; font-weight: 800; color: #ef4444;">${costo_iva:,.2f}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("🧪 Rentabilidad Específica por Perfume")
            if "Proveedor" in df_todas.columns:
                df_perfumes = df_todas.groupby(["Proveedor", "Producto"]).agg({
                    "Total_Venta": ["count", "sum"],
                    "Costo_Producto": "sum",
                    "IVA_(16%)": "sum",
                    "Comision_Generada": "sum",
                    "Utilidad_Neta": "sum"
                })
                # Aplanar los niveles del DataFrame generados por count/sum
                df_perfumes.columns = ["Unidades_Vendidas", "Bruto_Ingresado", "Inversion_Total", "IVA_Retenido", "Comisiones_Pagadas", "Utilidad_Real_Meta"]
                df_perfumes = df_perfumes.reset_index().sort_values(by="Utilidad_Real_Meta", ascending=False)
                
                for _, r in df_perfumes.iterrows():
                    st.markdown(f"""
                    <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid #8b5cf6; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                        <div style="font-size: 15px; font-weight: bold; color: #1e293b; margin-bottom: 4px;">🧪 {r['Proveedor']} - {r['Producto']}</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px;">
                            <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Unidades (Ingreso)</span><br><span style="font-size: 15px; font-weight: 800; color: #0f172a;">{r['Unidades_Vendidas']} ud / ${r['Bruto_Ingresado']:,.2f}</span></div>
                            <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Ganancia Real Neta</span><br><span style="font-size: 15px; font-weight: 800; color: #10b981;">${r['Utilidad_Real_Meta']:,.2f}</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.subheader("⚠️ Alertas de Deudores")
            
            df_adeudos = df_todas[df_todas["Estado_Venta"] == "Adeudo"].copy()
            if not df_adeudos.empty:
                # Sort initially by days since last payment descending
                df_adeudos = df_adeudos.sort_values(by="Dias_Ultimo_Abono", ascending=False)
                
                def highlight_deudas(row):
                    dias = row["Dias_Ultimo_Abono"]
                    try:
                        dias = int(dias)
                        if dias > 30:
                            return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row) # Rojo
                        elif dias >= 20: 
                            return ['background-color: rgba(255, 204, 0, 0.3)'] * len(row) # Amarillo
                        else:
                            return ['background-color: rgba(75, 255, 75, 0.3)'] * len(row) # Verde
                    except:
                        return [''] * len(row)
                
                # Select only the relevant columns for this alert table
                columnas_mostrar = ["ID_Venta", "Nombre_Vendedor", "Cliente", "Producto", "Dias_Ultimo_Abono", "Saldo_Pendiente", "Total_Abono"]
                df_adeudos_mostrar = df_adeudos[columnas_mostrar]
                
                for _, r in df_adeudos_mostrar.iterrows():
                    dias = 0
                    try:
                        dias = int(r['Dias_Ultimo_Abono'])
                    except:
                        pass
                    
                    if dias > 30:
                        color = "#ef4444" # Rojo
                        bg_accent = "rgba(239, 68, 68, 0.15)"
                    elif dias >= 20:
                        color = "#f59e0b" # Amarillo
                        bg_accent = "rgba(245, 158, 11, 0.15)"
                    else:
                        color = "#10b981" # Verde
                        bg_accent = "rgba(16, 185, 129, 0.15)"

                    st.markdown(f"""
                    <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid {color}; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div style="font-size: 16px; font-weight: 900; color: #1e293b;">👤 {r['Cliente']}</div>
                            <div style="font-size: 11px; font-weight: 800; color: {color}; background-color: {bg_accent}; padding: 3px 8px; border-radius: 12px; white-space: nowrap;">🚨 {dias} Días atraso</div>
                        </div>
                        <div style="font-size: 13px; color: #64748b; font-weight: 600; margin-bottom: 10px;">🏷️ {r['Producto']} (Vendedor: {r['Nombre_Vendedor']})</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                            <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Total Abonado</span><br><span style="font-size: 15px; font-weight: 800; color: #0f172a;">${r['Total_Abono']:,.2f}</span></div>
                            <div><span style="font-size: 12px; color: #4b5563; font-weight: 600;">Resta a Cobrar</span><br><span style="font-size: 15px; font-weight: 800; color: #ef4444;">${r['Saldo_Pendiente']:,.2f}</span></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("¡Excelente! No hay clientes con adeudos pendientes.")
            
            st.markdown("---")
            st.subheader("Tabla Global de Ventas")
            st.dataframe(df_todas)
        else:
            st.info("No hay ventas registradas aún.")

    with tab2:
        st.subheader("Actualizar Inventario por Vendedor")
        st.info("Asigna productos, precios y stock específico a cada vendedor/a.")
        
        from database import Usuario
        session = db.get_session()
        vendedores = session.query(Usuario).filter_by(rol="Vendedor").all()
        session.close()
        
        if vendedores:
            opciones_vnd = {v.email: v.nombre for v in vendedores}
            vendedor_sel_email = st.selectbox("Seleccionar Vendedor/a", options=list(opciones_vnd.keys()), format_func=lambda x: opciones_vnd[x])
            
            # Cargar su inventario actual
            df_inventario = db.leer_inventario(vendedor_email=vendedor_sel_email)
            
            # Formatear el Dataframe para el Data Editor (Agregando Costo Compra y Proveedor por ser Admin)
            if not df_inventario.empty:
                columnas = ["nombre", "precio"]
                if "costo_compra" in df_inventario.columns: columnas.append("costo_compra")
                if "proveedor" in df_inventario.columns: columnas.append("proveedor")
                columnas.append("stock")
                df_editor = df_inventario[columnas].copy()
            else:
                df_editor = pd.DataFrame(columns=["nombre", "precio", "costo_compra", "proveedor", "stock"])
                
            edited_df = st.data_editor(
                df_editor, 
                num_rows="dynamic", 
                width="stretch",
                column_config={
                    "nombre": st.column_config.TextColumn("Nombre del Producto", required=True),
                    "precio": st.column_config.NumberColumn("Precio Final ($)", min_value=0.0, format="%.2f", required=False),
                    "costo_compra": st.column_config.NumberColumn("Costo Compra ($)", min_value=0.0, format="%.2f", required=False),
                    "proveedor": st.column_config.TextColumn("Proveedor", required=False),
                    "stock": st.column_config.NumberColumn("Unidades Físicas", min_value=0, step=1, required=False)
                }
            )
            
            if st.button("💾 Guardar Inventario de " + opciones_vnd[vendedor_sel_email]):
                 exito, msj = db.guardar_inventario(edited_df, vendedor_sel_email)
                 if exito:
                     st.success(f"¡Inventario de {opciones_vnd[vendedor_sel_email]} guardado y sincronizado!")
                     st.rerun()
                 else:
                     st.error(msj)
        else:
            st.warning("No hay vendedores registrados en el sistema.")

    with tab3:
        st.subheader("Registrar Nuevo Abono a Cuenta")
        # Desplegable inteligente de deudores
        # df_todas lo reusamos de arriba
        df_ventas = df_todas
        if not df_ventas.empty:
            df_deudores = df_ventas[df_ventas["Estado_Venta"] == "Adeudo"]
            
            if not df_deudores.empty:
                opciones_ventas = {}
                for idx, row in df_deudores.iterrows():
                    desc = f"ID: {row['ID_Venta']} | Cliente: {row['Cliente']} | {row['Producto']} | Vend: {row['Nombre_Vendedor']} (Resta: ${row['Saldo_Pendiente']:,.2f})"
                    opciones_ventas[row['ID_Venta']] = desc
                    
                venta_buscada = st.selectbox(
                    "Selecciona o busca la cuenta por cobrar",
                    options=list(opciones_ventas.keys()),
                    format_func=lambda x: opciones_ventas[x]
                )
                
                if venta_buscada:
                    venta = df_ventas[df_ventas["ID_Venta"] == venta_buscada]
                    info = venta.iloc[0]
                    
                    with st.form("abono_form"):
                        monto_abono = st.number_input("Monto Recibido", min_value=1.0, max_value=float(info['Saldo_Pendiente']), step=100.0)
                        metodo_pago = st.selectbox("Método de Pago", ["Efectivo", "Transferencia", "Tarjeta"])
                        btn_abonar = st.form_submit_button("Confirmar Abono ($)")
                        
                        if btn_abonar:
                            exito, msj = db.registrar_abono(int(venta_buscada), monto_abono, metodo_pago)
                            if exito:
                                st.success(f"Abono por ${monto_abono:,.2f} registrado exitosamente.")
                                st.rerun()
                            else:
                                st.error(msj)
            else:
                st.success("¡Excelente! No hay ninguna cuenta con saldo pendiente por cobrar en el sistema.")
        else:
            st.info("Aún no hay ventas registradas.")

        st.markdown("---")
        st.subheader("Liquidación de Comisiones a Vendedores")
        st.write("Selecciona una venta liquidadada para registrar que ya le entregaste físicamente la comisión al vendedor.")
        
        if not df_todas.empty:
            df_por_pagar_admin = df_todas[(df_todas["Estado_Venta"] == "Pagado") & (df_todas["Comision_Fisicamente_Cobrada"] == False)]
            
            if not df_por_pagar_admin.empty:
                st.dataframe(df_por_pagar_admin[["ID_Venta", "Nombre_Vendedor", "Cliente", "Producto", "Comision_Generada"]], hide_index=True)
                
                opciones_admin = {}
                for idx, row in df_por_pagar_admin.iterrows():
                    desc_admin = f"Venta #{row['ID_Venta']} | {row['Nombre_Vendedor']} | Com: ${row['Comision_Generada']:,.2f}"
                    opciones_admin[row['ID_Venta']] = desc_admin
                
                with st.form("form_admin_pagar_comision"):
                    venta_sel_admin = st.selectbox(
                        "Selecciona la comisión a marcar como liquidada", 
                        options=list(opciones_admin.keys()),
                        format_func=lambda x: opciones_admin[x]
                    )
                    btn_pagar_comision = st.form_submit_button("Marcar comisión como ENTREGADA")
                    
                    if btn_pagar_comision:
                        exito_c, msj_c = db.marcar_comision_cobrada(venta_sel_admin)
                        if exito_c:
                            st.success(f"¡Éxito! {msj_c}")
                            st.rerun()
                        else:
                            st.error(msj_c)
            else:
                st.success("Al día de hoy no tienes ninguna comisión pendiente de entregar a tus vendedores.")
        else:
            st.info("No hay ventas en el sistema.")

    with tab4:
        st.subheader("Invitar Nuevo Vendedor al Sistema")
        st.markdown("Registra al vendedor y envíale automáticamente su acceso al correo de Gmail.")

        with st.form("invitar_vendedor_form"):
            nuevo_nombre = st.text_input("Nombre completo del vendedor")
            nuevo_correo = st.text_input("Correo Electrónico (Gmail)")
            nueva_comision = st.number_input("Tasa de Comisión (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5)
            
            tipo_vendedor_val = st.radio("Modalidad de Ventas Permitida", ["Crédito", "One-Shot"], 
                                         help="Crédito permite a este vendedor dejar ventas con abonos pendientes. One-Shot forzará a que el vendedor solo pueda registrar ventas 100% liquidadas.", horizontal=True)
            
            st.divider()
            
            vendedores_actuales = db.obtener_vendedores()
            opciones_patrocinador = ["Ninguno (Empresa)"] + [st.session_state.user_email] + vendedores_actuales["email"].tolist()
            # Eliminar duplicados manteniendo orden
            opciones_patrocinador = list(dict.fromkeys(opciones_patrocinador))
            
            patrocinador_val = st.selectbox("Patrocinador (Líder de Red que ganará 5% de esta persona)", opciones_patrocinador, index=opciones_patrocinador.index(st.session_state.user_email) if st.session_state.user_email in opciones_patrocinador else 0)

            btn_invitar = st.form_submit_button("Generar Credencial y Enviar Invitación")

            if btn_invitar:
                if not nuevo_nombre or not nuevo_correo:
                    st.error("Nombre y correo son obligatorios.")
                elif "@" not in nuevo_correo:
                    st.error("Por favor ingresa un correo electrónico válido.")
                else:
                    import random
                    import string
                    from email_service import enviar_invitacion_gmail
                    
                    # Limpiar patrocinador
                    final_patrocinador = None if patrocinador_val == "Ninguno (Empresa)" else patrocinador_val

                    # Generar contraseña temporal segura
                    caracteres = string.ascii_letters + string.digits
                    password_temp = "".join(random.choice(caracteres) for i in range(8))
                    
                    # Guardar en SQLite el nuevo usuario
                    exito_db, msj_db = db.registrar_vendedor(nuevo_nombre, nuevo_correo, password_temp, nueva_comision, final_patrocinador, tipo_vendedor_val)
                    
                    if exito_db:
                        st.info("Generando credenciales y conectando con el servicio de correo...")
                        
                        # Enviar el correo electrónico
                        exito_mail, mensaje_mail = enviar_invitacion_gmail(nuevo_correo, nuevo_nombre, password_temp)
                        
                        if exito_mail:
                            st.success(f"¡Vendedor registrado exitosamente! Se ha enviado la invitación a {nuevo_correo}")
                            st.code(f"Contraseña temporal generada: {password_temp}", language="text")
                        else:
                            st.error(f"El vendedor fue guardado en BD PERO no se pudo enviar el correo: {mensaje_mail}")
                            st.markdown("Revisa el archivo `.streamlit/secrets.toml`.")
                    else:
                        st.error(f"Error al registrar en la base de datos: {msj_db}")

    with tab5:
        st.subheader("🕵️ Buscador Inteligente para Correcciones")
        st.markdown("Busca cualquier registro rápidamente para modificarlo o eliminarlo permanentemente del sistema sin dejar basura ni descuadrar tus inventarios.")
        tipo_correccion = st.radio("¿Qué tipo de registro deseas corregir?", ["Ventas", "Abonos"], horizontal=True)
        
        busqueda = st.text_input("🔍 Escribe para buscar...", placeholder="Por ejemplo: Maria, 45, o nombre de producto", key="buscador_admin")
        termino = str(busqueda).lower() if busqueda else ""
        
        if tipo_correccion == "Ventas":
            if not df_todas.empty:
                df_filtro = df_todas
                
                if termino:
                    df_filtro = df_todas[
                        df_todas["Cliente"].astype(str).str.lower().str.contains(termino) |
                        df_todas["Nombre_Vendedor"].astype(str).str.lower().str.contains(termino) |
                        df_todas["ID_Venta"].astype(str).str.lower().str.contains(termino) |
                        df_todas["Producto"].astype(str).str.lower().str.contains(termino)
                    ]
                
                # Para evitar lag en mobile si hay 2000 ventas, mostramos máximo las 30 más recientes que coincidan
                df_filtro = df_filtro.sort_values(by="ID_Venta", ascending=False).head(30)
                
                if not df_filtro.empty:
                    st.markdown(f"*{f'Mostrando {len(df_filtro)} resultados' if termino else 'Mostrando las últimas 30 ventas registradas'}*")
                    for _, row in df_filtro.iterrows():
                        fecha_str = row.get('Fecha_Venta', '')
                        fecha_html = f"<span style='float:right; font-size:13px; font-weight:normal; color:#64748b;'>{fecha_str}</span>" if fecha_str else ""
                        
                        st.markdown(f'''
                        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid #3b82f6; margin-bottom: 10px;">
                            <div style="font-weight:bold; font-size:16px;">Venta #{row['ID_Venta']} - {row['Cliente']} {fecha_html}</div>
                            <div style="color: #475569; font-size: 14px; margin-bottom: 0px;">{row['Nombre_Vendedor']} vendió <b>{row.get('Cantidad', 1)}x {row['Producto']}</b> por <b>${row['Total_Venta']:,.2f}</b></div>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("✏️ Editar Completo", key=f"edit_v_{row['ID_Venta']}", use_container_width=True):
                                df_inventario = db.leer_inventario(vendedor_email=row['Vendedor_Email'])
                                dialog_editar_venta(row, df_inventario, db)
                        with cc2:
                            if st.button("🗑️ Eliminar y Devolver", key=f"del_v_{row['ID_Venta']}", type="primary", use_container_width=True):
                                exito, msj = db.eliminar_venta(row['ID_Venta'])
                                if exito: 
                                    st.success(msj)
                                    st.rerun()
                                else: 
                                    st.error(msj)
                        st.markdown("<br>", unsafe_allow_html=True)
                else:
                    st.warning("No se encontró ninguna Venta coincidente.")
        else:
            if not df_abonos_global.empty:
                # Mergeamos antes de filtrar para que el buscador encuentre nombres de cliente
                if not df_todas.empty:
                    df_ab_enrich = pd.merge(
                        df_abonos_global,
                        df_todas[["ID_Venta", "Cliente", "Producto", "Nombre_Vendedor"]],
                        left_on="venta_id",
                        right_on="ID_Venta",
                        how="left"
                    )
                else:
                    df_ab_enrich = df_abonos_global
                    
                df_filtro = df_ab_enrich
                
                if termino:
                    df_filtro = df_ab_enrich[
                        df_ab_enrich["id_abono"].astype(str).str.lower().str.contains(termino) |
                        df_ab_enrich["venta_id"].astype(str).str.lower().str.contains(termino) |
                        df_ab_enrich["monto_abono"].astype(str).str.lower().str.contains(termino) |
                        df_ab_enrich.get("Cliente", pd.Series(dtype=str)).astype(str).str.lower().str.contains(termino) |
                        df_ab_enrich.get("Nombre_Vendedor", pd.Series(dtype=str)).astype(str).str.lower().str.contains(termino)
                    ]
                
                # Acotar resultados 
                df_filtro = df_filtro.sort_values(by="id_abono", ascending=False).head(30)
                
                if not df_filtro.empty:
                    st.markdown(f"*{f'Mostrando {len(df_filtro)} abonos' if termino else 'Mostrando los últimos 30 abonos registrados'}*")
                    for _, row in df_filtro.iterrows():
                        venta_id_asociada = row['venta_id']
                        
                        info_cl = row.get("Cliente", "Cliente Desconocido") if pd.notna(row.get("Cliente")) else "Cliente Desconocido"
                        info_prod = row.get("Producto", "Producto Desconocido") if pd.notna(row.get("Producto")) else "Producto Desconocido"
                        vendedor = row.get("Nombre_Vendedor", "Vendedor Desconocido") if pd.notna(row.get("Nombre_Vendedor")) else "Vendedor Desconocido"
                        
                        # Extraer fecha del abono
                        fecha_ab = row.get('fecha_abono')
                        fecha_ab_str = fecha_ab.strftime("%d-%b-%Y") if pd.notna(fecha_ab) and hasattr(fecha_ab, 'strftime') else ""
                        fecha_html = f"<span style='float:right; font-size:13px; font-weight:normal; color:#64748b;'>{fecha_ab_str}</span>" if fecha_ab_str else ""
                                
                        st.markdown(f'''
                        <div style="background-color: #f8fafc; padding: 15px; border-radius: 8px; border-left: 5px solid #10b981; margin-bottom: 10px;">
                            <div style="font-weight:bold; font-size:16px;">Abono #{row['id_abono']} <span style="font-size:13px; font-weight:normal; color:#64748b;">(De la Venta #{venta_id_asociada})</span> {fecha_html}</div>
                            <div style="color: #475569; font-size: 14px; margin-bottom: 4px;">Depositado por: <b>{info_cl}</b> ({info_prod})</div>
                            <div style="color: #64748b; font-size: 12px; margin-bottom: 8px;">Cobrador/Gestor: {vendedor}</div>
                            <div style="color: #047857; font-size: 18px; font-weight:900; margin-bottom: 0px;">+ ${row['monto_abono']:,.2f} <span style="font-size:13px; font-weight:normal; color:#64748b;">({row['metodo_pago']})</span></div>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            if st.button("✏️ Modificar Abono", key=f"edit_a_{row['id_abono']}", use_container_width=True):
                                dialog_editar_abono(row, db)
                        with cc2:
                            if st.button("🗑️ Eliminar Abono", key=f"del_a_{row['id_abono']}", type="primary", use_container_width=True):
                                exito, msj = db.eliminar_abono(row['id_abono'])
                                if exito:
                                    st.success(msj)
                                    st.rerun()
                                else:
                                    st.error(msj)
                        st.markdown("<br>", unsafe_allow_html=True)
                else:
                    st.warning("No se encontró ningún Abono coincidente.")
