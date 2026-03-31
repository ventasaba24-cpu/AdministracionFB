import streamlit as st
import pandas as pd
import extra_streamlit_components as stx
import datetime

# Inicializar un único Cookie Manager por ejecución
def get_manager():
    return stx.CookieManager(key="auth_cookie_manager")

def check_password():
    """Returns `True` if the user is authenticated."""
    cookie_manager = get_manager()

    # Procesar la orden de cerrar sesión de la corrida anterior
    if st.session_state.get("wants_logout", False):
        try:
            cookie_manager.delete("session_token")
        except KeyError:
            pass
        # Destruir todas las variables excepto cookie_manager (para que no colapse)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.logged_in = False
        # No usamos st.rerun, dejamos que la página termine de cargar la pantalla de login natural
        # Así el navegador SÍ procesa la orden de borrado de cookie antes de que el usuario haga otra cosa.
        st.success("Sesión cerrada correctamente.")

    # Get cookie token if exists
    user_token = cookie_manager.get(cookie="session_token")

    # If the user has a token but is not logged in yet (this happens on the second tick after a refresh)
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
            st.rerun() # Refresh to update UI cleanly now that we are logged in
        else:
            # Token is invalid, remove it
            try:
                cookie_manager.delete("session_token")
            except:
                pass
            st.session_state.logged_in = False

    # Initialize empty session state if it wasn't done
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.user_name = ""
        st.session_state.user_role = ""
        st.session_state.user_comision = 0.0

    if st.session_state.get("logged_in", False):
        return True

    # Login form
    st.title("Acceso al Sistema ERP")
    st.markdown("Por favor, ingresa tus credenciales.")
    
    with st.form("login_form"):
        username = st.text_input("Correo Electrónico (Gmail)")
        password = st.text_input("Contraseña", type="password")
        submit_button = st.form_submit_button("Entrar")

    if submit_button:
        # Importar y usar la conexión a DB
        from database import DatabaseHandler
        db = DatabaseHandler()
        
        is_valid, user = db.login(username, password)
        
        if is_valid:
            # Set cookie for 7 days
            expire_date = datetime.datetime.now() + datetime.timedelta(days=7)
            cookie_manager.set("session_token", user.email, expires_at=expire_date)
            
            st.session_state.logged_in = True
            st.session_state.user_name = user.nombre
            st.session_state.user_role = user.rol
            st.session_state.user_comision = user.tasa_comision
            st.session_state.user_email = user.email
            st.success("Acceso concedido. Cargando...")
            st.rerun()
        else:
            st.error("😕 Correo o contraseña incorrectos.")

    return False

def logout():
    # En lugar de destruir el estado agresivamente aquí, levantamos bandera
    st.session_state.wants_logout = True
    st.rerun()
