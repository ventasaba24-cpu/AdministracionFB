import streamlit as st
from auth import check_password, logout
import pages.vendedor as vendedor_page
import pages.admin as admin_page

# Page config debe ser el primer llamado a st en aplicación principal
st.set_page_config(
    page_title="Portal Extranet de Colaboradores",
    page_icon="🏢",
    layout="centered", # Centered funciona marginalmente mejor para enfocar contenido en celular
    initial_sidebar_state="collapsed" # Es crítico colapsar el menú lateral en celular por defecto para ahorrar y aprovechar pantalla
)

import urllib.request
def verificar_geo_bloqueo():
    # Solo ejecutar la validacion una vez por sesion
    if "geo_validado_js" not in st.session_state:
        st.session_state.geo_bloqueado = False
        
        try:
            from streamlit_javascript import st_javascript
            
            # Ejecutamos JS en el navegador para consultar el país (saltando proxies de Streamlit)
            js_code = """
            await fetch('https://ipapi.co/json/')
                .then(response => response.json())
                .then(data => data.country_code)
                .catch(error => 'ERROR')
            """
            
            # Mostrar un pequeño loader mientras esperamos (solo tarda ~300ms)
            with st.spinner("Estableciendo conexión encriptada..."):
                country_code = st_javascript(js_code)
                
            # st_javascript regresa 0 mientras evalúa. Detenemos la UI temporalmente.
            if country_code == 0:
                st.stop()
                
            # Evaluamos la respuesta
            if country_code == "ERROR" or not country_code:
                # Opción B Flexible: Si tiene AdBlocker o falla la red, no bloqueamos
                st.session_state.geo_bloqueado = False
            else:
                # ATENCION: Dejado temporalmente en == "MX" para que lo pruebes desde Mexico
                if country_code == "MX":
                    st.session_state.geo_bloqueado = True
                else:
                    st.session_state.geo_bloqueado = False
                    
        except ImportError:
            # Si no está instalada la librería en desarrollo local, dejar pasar
            st.session_state.geo_bloqueado = False
            
        st.session_state.geo_validado_js = True

    if st.session_state.geo_bloqueado:
        # Inyectamos CSS para ocultar TODO el diseño de Streamlit y simular página caída
        st.markdown("""
        <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            .stApp {background-color: white;}
            .block-container {padding-top: 1rem; max-width: 100%;}
        </style>
        <div style="font-family: monospace; font-size: 24px; font-weight: bold; margin-bottom: 10px;">404 Not Found</div>
        <div style="font-family: monospace; font-size: 14px; text-align: left;">nginx/1.18.0 (Ubuntu)</div>
        <hr style="border: 0; border-top: 1px solid #ccc; margin-top: 5px;">
        """, unsafe_allow_html=True)
        st.stop()

verificar_geo_bloqueo()

# Custom CSS basico para mejorar el look en celulares especialmente
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .sidebar .sidebar-content {
        background: #ffffff;
    }
    /* Hacer que los botones usen todo el ancho en mobile para facilitar toques dactilares */
    div[data-testid="stButton"] button {
        width: 100%; 
        padding-top: 0.75rem;
        padding-bottom: 0.75rem;
        font-weight: bold;
    }
    /* Las métricas deben respirar mas en mobile */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    /* Ocultar el menú lateral automático de Streamlit (páginas) */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Funciones de envoltura para llamar a las páginas
def run_vendedor_page():
    vendedor_page.show()

def run_admin_page():
    admin_page.show()

def run_contador_page():
    import pages.contador as contador_page
    contador_page.show()

def main():
    if not check_password():
        st.stop()  # Detener la ejecución si no está logueado

    # Si llega aquí, está logueado
    st.sidebar.title(f"Bienvenido, {st.session_state.user_name}")
    st.sidebar.markdown(f"**Rol:** {st.session_state.user_role}")
    
    st.sidebar.markdown("---")
    
    # Navegación basada en roles
    pages = {}
    
    if st.session_state.user_role == "Admin":
        st.sidebar.success("Modo Administrador Activo")
        page_names_to_funcs = {
            "🏠 Dashboard Vendedor": run_vendedor_page,
            "📊 Panel de Administración": run_admin_page
        }
    elif st.session_state.user_role == "Vendedor":
        st.sidebar.info("Modo Vendedor Activo")
        page_names_to_funcs = {
            "🏠 Dashboard Vendedor": run_vendedor_page
        }
    elif st.session_state.user_role == "Contador":
        st.sidebar.success("Modo Contable Activo")
        page_names_to_funcs = {
            "📊 Panel Contable": run_contador_page
        }
    else:
        st.error("Rol no reconocido.")
        st.stop()

    demo_name = st.sidebar.radio("Navegación", list(page_names_to_funcs.keys()))
    
    st.sidebar.markdown("---")
    if st.sidebar.button("Cerrar Sesión"):
        logout()

    # Ejecutar la página seleccionada
    page_names_to_funcs[demo_name]()

if __name__ == "__main__":
    main()
