import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

def enviar_invitacion_gmail(destinatario_email, nombre_vendedor, password_temporal):
    """
    Envía un correo de invitación al vendedor con su contraseña temporal.
    Requiere que se configure el email emisor y el app password en st.secrets o variables de entorno.
    """
    try:
        # Intentar obtener credenciales de st.secrets
        # Necesitarás crear un archivo .streamlit/secrets.toml con estas llaves
        # o configurarlas directamente en el código para pruebas (¡no recomendado para producción!)
        try:
            remitente_email = st.secrets["email"]["user"]
            remitente_password = st.secrets["email"]["password"]
        except (KeyError, FileNotFoundError):
            # Fallback para pruebas si no hay st.secrets configurado
            # DEBES REEMPLAZAR ESTO CON TUS DATOS REALES DE PRUEBA
            # st.error("Por favor configura tus credenciales de Gmail en .streamlit/secrets.toml")
            remitente_email = "tu_gmail@gmail.com"  # <- CAMBIAR
            remitente_password = "tu_app_password"  # <- CAMBIAR (contraseña de aplicación, no la principal)
            
            # Para la demo vamos a simplemente simular el envío exitoso si no han puesto credenciales
            if remitente_email == "tu_gmail@gmail.com":
                 # Simulate sending email
                 print(f"SIMULACIÓN DE ENVÍO: Correo a {destinatario_email} con contraseña {password_temporal}")
                 return True, "Simulación exitosa (Configura tu Gmail real para enviar de verdad)"

        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = "¡Bienvenido! Tu acceso al panel de Ventas ERP"
        mensaje["From"] = remitente_email
        mensaje["To"] = destinatario_email

        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #4CAF50;">¡Hola {nombre_vendedor}!</h2>
                <p>El administrador te ha invitado al sistema de <b>Gestión de Ventas e Inventario</b>.</p>
                <p>Usa la siguiente información para iniciar sesión:</p>
                <div style="background-color: #f4f4f4; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><b>📍 Enlace de acceso:</b> (Pide al administrador el enlace de la aplicación web)</p>
                    <p><b>✉️ Tu Correo:</b> {destinatario_email}</p>
                    <p><b>🔑 Contraseña Temporal:</b> <span style="background: yellow; padding: 3px;">{password_temporal}</span></p>
                </div>
                <p>Por favor, ingresa al sistema y registra tus ventas allí.</p>
                <p><i>- El equipo de Administración</i></p>
            </body>
        </html>
        """
        
        parte_html = MIMEText(html_content, "html")
        mensaje.attach(parte_html)

        # Configurar conexión SMTP con Gmail
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(remitente_email, remitente_password)
        server.sendmail(remitente_email, destinatario_email, mensaje.as_string())
        server.quit()
        
        return True, "Mensaje enviado correctamente vía Gmail."

    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación. Verifica que tu App Password sea correcto."
    except Exception as e:
        return False, f"Error al enviar correo: {e}"
