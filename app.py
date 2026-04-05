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
</style>
""", unsafe_allow_html=True)

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
        # En Streamlit clásico con carpeta pages/, no necesitamos un selector explícito
        # si solo cargamos el contenido aquí, o podemos usar el selector como "radio"
        # Para hacer un switch real sin depender del autoscan de Streamlit de la carpeta 'pages':
        
        # Opcion 1: usar selectbox nativo
        page_names_to_funcs = {
            "🏠 Dashboard Vendedor": run_vendedor_page,
            "📊 Panel de Administración": run_admin_page
        }
    elif st.session_state.user_role == "Vendedor":
        st.sidebar.info("Modo Vendedor Activo")
        page_names_to_funcs = {
            "🏠 Dashboard Vendedor": run_vendedor_page
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

# Funciones de envoltura para llamar a las páginas
def run_vendedor_page():
    vendedor_page.show()

def run_admin_page():
    admin_page.show()

if __name__ == "__main__":
    main()
