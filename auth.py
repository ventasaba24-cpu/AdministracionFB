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

    # Quitado bloque de sleep para evitar colgar el frontend.
    # Procesar la orden de cerrar sesión de la corrida anterior
    if st.session_state.get("wants_logout", False):
        try:
            cookie_manager.delete("session_token")
        except KeyError:
            pass
            
        st.query_params.clear()
            
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.session_state.logged_in = False
        
        # Inyectar una instrucción Javascript directa al navegador para forzar 
        # un F5 real (Refresh). Esto vacía la memoria persistente que causa el auto-login.
        import streamlit.components.v1 as components
        components.html("""
            <script>
            setTimeout(function() {
                window.parent.location.href = window.parent.location.pathname;
            }, 500);
            </script>
        """, height=0)
        
        st.info("🔄 Cerrando sesión, por favor espera...")
        st.stop() # Abortamos ejecución para dar tiempo al JS de recargar la página

    # MÉTODO INFALIBLE PARA CELULARES (Evita bloqueo ITP de Safari/iOS)
    # Streamlit guarda estos parámetros en la barra de direcciones que nunca se borra con un F5.
    user_token = st.query_params.get("session_token", None)

    # Get cookie token if exists (Priorizando el método nativo súper rápido de Streamlit 1.35+)
    if not user_token:
        if hasattr(st, "context") and hasattr(st.context, "cookies"):
            user_token = st.context.cookies.get("session_token")
        if not user_token:
            # Fallback al cookie manager asíncrono si es versión antigua
            user_token = cookie_manager.get(cookie="session_token")

    # If the user has a token but is not logged in yet (this happens on refresh)
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
            st.rerun() # Refresh to clear login screen
        else:
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
            # A veces viene en un array o separada por comas, tomamos la primera si es que existe
            x_forwarded = st.context.headers.get("X-Forwarded-For")
            if x_forwarded:
                client_ip = x_forwarded.split(',')[0].strip()
            else:
                client_ip = st.context.headers.get("X-Real-IP", "Desconocida")

        # Importar y usar la conexión a DB
        from database import DatabaseHandler
        db = DatabaseHandler()
        
        is_valid, user, msj_respuesta = db.login_seguro(username, password, client_ip)
        
        if is_valid:
            # Set cookie for 10 days! (Garantiza sesión de más de una semana)
            expire_date = datetime.datetime.now() + datetime.timedelta(days=10)
            cookie_manager.set("session_token", user.email, expires_at=expire_date)
            # MÉTODO CELULAR: Colocar la sesión en la URL (No falla ante el bloqueo de Apple a Iframes)
            st.query_params["session_token"] = user.email
            
            st.session_state.logged_in = True
            st.session_state.user_name = user.nombre
            st.session_state.user_role = user.rol
            st.session_state.user_comision = user.tasa_comision
            st.session_state.user_email = user.email
            
            box_login.empty() # Destruir el formulario de la UI
            return True # Retornar positivo para que app.py dibuje, permitiendo que la App mande la nueva URL sin abortar ejecución
        else:
            st.error(f"❌ {msj_respuesta}")

    return False

def logout():
    # Levantamos bandera
    st.session_state.wants_logout = True
    st.rerun()
