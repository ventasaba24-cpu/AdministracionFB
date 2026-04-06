import streamlit as st
import pandas as pd
import datetime

def check_password():
    """Returns `True` if the user is authenticated."""
    # Procesar orden de cerrar sesión de la corrida anterior
    if st.session_state.get("wants_logout", False):
        st.query_params.clear()
            
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.session_state.logged_in = False
        
        # Al limpiarse el query param y el state, rerun lo lanzará al login nativamente
        st.rerun()

    # MÉTODO INFALIBLE PARA CELULARES Y NUBE:
    # Utilizar exclusivamente la Barra de Direcciones nativa, sin librerías externas de cookies propensas al lag.
    user_token = st.query_params.get("session_token", None)

    # Si el usuario tiene un token pero acaba de hacer un F5 (refresh)
    if user_token and not st.session_state.get("logged_in", False):
        from database import DatabaseHandler
        db = DatabaseHandler()
        user = db.get_user_by_email(user_token)
        
        if user:
            st.session_state.logged_in = True
            st.session_state.user_name = user.nombre
            st.session_state.user_role = user.rol
            st.session_state.user_comision = user.tasa_comision
            st.session_state.user_email = user.email
            st.session_state.user_tipo_vendedor = user.tipo_vendedor
            st.rerun() # Refresh silencioso
        else:
            st.query_params.clear()
            st.session_state.logged_in = False

    # Inicializar memoria para la navegación
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.session_state.user_role = ""
        st.session_state.user_comision = 0.0

    if st.session_state.get("logged_in", False):
        return True

    # Login form (Ofuscado intencionalmente por seguridad)
    box_login = st.empty()
    with box_login.container():
        st.title("FB-Catalogo")
        st.markdown("Plataforma de consulta restringida.")
        
        with st.form("login_form"):
            username = st.text_input("Correo Asignado")
            password = st.text_input("Token de Seguridad", type="password")
            submit_button = st.form_submit_button("Validar Acceso")

    if submit_button:
        # Extraer IP remota para el candado de seguridad
        client_ip = "Desconocida"
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            x_forwarded = st.context.headers.get("X-Forwarded-For")
            if x_forwarded:
                client_ip = x_forwarded.split(',')[0].strip()
            else:
                client_ip = st.context.headers.get("X-Real-IP", "Desconocida")

        # Autenticación segura local vs DB
        from database import DatabaseHandler
        db = DatabaseHandler()
        
        is_valid, user, msj_respuesta = db.login_seguro(username, password, client_ip)
        
        if is_valid:
            # MÉTODO NATIVO (100% estable en iOS/Android y sin ventanas emergentes de error de iFrames)
            st.query_params["session_token"] = user.email
            
            st.session_state.logged_in = True
            st.session_state.user_name = user.nombre
            st.session_state.user_role = user.rol
            st.session_state.user_comision = user.tasa_comision
            st.session_state.user_email = user.email
            st.session_state.user_tipo_vendedor = user.tipo_vendedor
            
            box_login.empty() # Destruir formulario de la pantalla
            return True 
        else:
            st.error(f"❌ {msj_respuesta}")

    return False

def logout():
    # Levantamos bandera
    st.session_state.wants_logout = True
    st.rerun()
