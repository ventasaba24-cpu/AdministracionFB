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
import json

def verificar_geo_bloqueo():
    if "geo_validado" not in st.session_state:
        st.session_state.geo_bloqueado = False
        try:
            if hasattr(st, 'context') and hasattr(st.context, 'headers'):
                headers = st.context.headers
                ip_list = headers.get("X-Forwarded-For", "127.0.0.1")
                client_ip = ip_list.split(",")[0].strip()
                
                if client_ip not in ["127.0.0.1", "localhost", "::1"]:
                    url = f"http://ip-api.com/json/{client_ip}?fields=status,countryCode"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=3) as response:
                        data = json.loads(response.read().decode())
                        if data.get("status") == "success" and data.get("countryCode") != "MX":
                            st.session_state.geo_bloqueado = True
        except Exception:
            # Opción B (Acceso Flexible): Si la API falla o hay timeout, no bloqueamos (Fail-Open)
            pass
            
        st.session_state.geo_validado = True

    if st.session_state.geo_bloqueado:
        st.markdown("<h1 style='text-align: center; color: #ef4444;'>🛑 ACCESO DENEGADO</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #475569;'>Restricción Geográfica</h3>", unsafe_allow_html=True)
        st.error("Por motivos de seguridad corporativa, el acceso a este ERP está restringido exclusivamente a dispositivos y redes operando dentro del territorio de **México**.")
        st.info("Su intento de conexión internacional ha sido bloqueado. Si cree que esto es un error, por favor contacte al Administrador y verifique que no está utilizando una VPN (Virtual Private Network).")
        st.stop()

# Ejecutar la barrera de seguridad de inmediato
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
