import streamlit as st
import pandas as pd

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
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard de KPIs", "📦 Gestión de Inventario", "💵 Abonos y Pagos", "✉️ Invitar Vendedor"])

    with tab1:
        st.subheader("Indicadores Clave de Desempeño")
        if not df_todas.empty:
            ventas_totales = df_todas["Total_Venta"].sum()
            producto_top = df_todas.groupby("Producto")["Total_Venta"].sum().idxmax() if not df_todas.empty else "N/A"
            vendedor_top = df_todas.groupby("Nombre_Vendedor")["Total_Venta"].sum().idxmax() if not df_todas.empty else "N/A"
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Ventas Totales Mensuales", f"${ventas_totales:,.2f}")
            col2.metric("Producto Top en Ingresos", producto_top)
            col3.metric("Vendedor Top", vendedor_top)
            
            st.markdown("---")
            st.subheader("Comisiones por Vendedor")
            df_com = df_todas.groupby("Nombre_Vendedor").agg({
                "Total_Venta": "sum",
                "Comision_Generada": "sum"
            }).reset_index()
            st.dataframe(df_com, hide_index=True, width="stretch")
            
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
                
                st.dataframe(df_adeudos_mostrar.style.apply(highlight_deudas, axis=1).format({"Saldo_Pendiente": "${:,.2f}", "Total_Abono": "${:,.2f}"}), width="stretch", hide_index=True)
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
            
            # Formatear el Dataframe para el Data Editor
            if not df_inventario.empty:
                df_editor = df_inventario[["nombre", "precio", "stock"]].copy()
            else:
                df_editor = pd.DataFrame(columns=["nombre", "precio", "stock"])
                
            edited_df = st.data_editor(
                df_editor, 
                num_rows="dynamic", 
                width="stretch",
                column_config={
                    "nombre": st.column_config.TextColumn("Nombre del Producto", required=True),
                    "precio": st.column_config.NumberColumn("Precio de Lista ($)", min_value=0.0, format="%.2f", required=False),
                    "stock": st.column_config.NumberColumn("Unidades Físicas (Stock)", min_value=0, step=1, required=False)
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
            nueva_comision = st.number_input("Tasa de Comisión (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.5)

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
                    
                    # Generar contraseña temporal segura
                    caracteres = string.ascii_letters + string.digits
                    password_temp = "".join(random.choice(caracteres) for i in range(8))
                    
                    # Guardar en SQLite el nuevo usuario
                    exito_db, msj_db = db.registrar_vendedor(nuevo_nombre, nuevo_correo, password_temp, nueva_comision)
                    
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

