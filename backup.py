import io
import datetime
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

def get_mexico_time():
    return datetime.datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)

def generar_excel_respaldo_completo(db):
    """
    Genera un archivo Excel en memoria con la copia EXACTA y COMPLETA de las 8 tablas de la Base de Datos:
    - Ventas
    - Abonos
    - Inventario
    - Usuarios
    - Gastos
    - Catalogo_Productos
    - Grupos_Inventario
    - Intentos_Seguridad
    """
    if hasattr(db, "get_session"):
        session = db.get_session()
    elif isinstance(db, tuple) and len(db) >= 2:
        session = db[1]()
    elif hasattr(db, "__call__"):
        session = db()
    else:
        from database import DatabaseHandler
        session = DatabaseHandler().get_session()
    try:
        from database import Venta, Abono, Producto, Usuario, Gasto, CatalogoProducto, GrupoInventario, IntentoSeguridad
        
        # 1. Ventas
        ventas = session.query(Venta).all()
        datos_ventas = []
        for v in ventas:
            datos_ventas.append({
                "ID_Venta": v.id,
                "Fecha_Venta": v.fecha_venta,
                "Vendedor_Email": v.vendedor_email,
                "Cliente": v.cliente,
                "Producto": v.producto_nombre,
                "Cantidad": v.cantidad,
                "Monto_Total": v.monto_total,
                "Costo_Historico": v.costo_historico,
                "Comision_Cobrada": v.comision_cobrada,
                "Fecha_Cobro_Comision": v.fecha_cobro_comision
            })
        df_ventas = pd.DataFrame(datos_ventas)

        # 2. Abonos
        abonos = session.query(Abono).all()
        datos_abonos = []
        for a in abonos:
            datos_abonos.append({
                "ID_Abono": a.id_abono,
                "ID_Venta": a.venta_id,
                "Fecha_Abono": a.fecha_abono,
                "Monto_Abono": a.monto_abono,
                "Metodo_Pago": a.metodo_pago,
                "Comprobante_Foto": a.comprobante_foto
            })
        df_abonos = pd.DataFrame(datos_abonos)

        # 3. Inventario
        prods = session.query(Producto).all()
        datos_prods = []
        for p in prods:
            datos_prods.append({
                "ID_Producto": p.id,
                "Nombre": p.nombre,
                "Vendedor_Email": p.vendedor_email,
                "Stock": p.stock,
                "Precio_Publico": p.precio,
                "Costo_Compra": p.costo_compra,
                "Proveedor": p.proveedor,
                "Lote": p.lote,
                "Fecha_Ingreso": p.fecha_ingreso
            })
        df_prods = pd.DataFrame(datos_prods)

        # 4. Usuarios (Copia exacta incluyendo Password Hash)
        users = session.query(Usuario).all()
        datos_users = []
        for u in users:
            datos_users.append({
                "ID_Usuario": u.id,
                "Nombre": u.nombre,
                "Email": u.email,
                "Password_Hash": u.password,
                "Rol": u.rol,
                "Tasa_Comision": u.tasa_comision,
                "Patrocinador_Email": u.patrocinador_email,
                "Tipo_Vendedor": u.tipo_vendedor,
                "Session_Token": u.session_token,
                "Grupo_Inventario_ID": u.grupo_inventario_id,
                "Ultimo_Login": u.ultimo_login
            })
        df_users = pd.DataFrame(datos_users)

        # 5. Gastos
        gastos = session.query(Gasto).all()
        datos_gastos = []
        for g in gastos:
            datos_gastos.append({
                "ID_Gasto": g.id,
                "Concepto": g.concepto,
                "Monto": g.monto,
                "Categoria": g.categoria,
                "Fecha_Gasto": g.fecha_gasto
            })
        df_gastos = pd.DataFrame(datos_gastos)

        # 6. Catálogo Maestro de Productos
        catalogo = session.query(CatalogoProducto).all()
        datos_cat = []
        for c in catalogo:
            datos_cat.append({
                "ID_Catalogo": c.id,
                "Nombre": c.nombre,
                "Categoria": c.categoria,
                "Descripcion": c.descripcion
            })
        df_catalogo = pd.DataFrame(datos_cat)

        # 7. Grupos de Inventario
        grupos = session.query(GrupoInventario).all()
        datos_grupos = []
        for grp in grupos:
            datos_grupos.append({
                "ID_Grupo": grp.id,
                "Nombre_Grupo": grp.nombre_grupo,
                "Fecha_Creacion": grp.fecha_creacion
            })
        df_grupos = pd.DataFrame(datos_grupos)

        # 8. Intentos de Seguridad
        seguridad = session.query(IntentoSeguridad).all()
        datos_seg = []
        for s in seguridad:
            datos_seg.append({
                "ID": s.id,
                "Identificador": s.identificador,
                "Fallos": s.fallos,
                "Bloqueado_Hasta": s.bloqueado_hasta,
                "Ultimo_Intento": s.ultimo_intento
            })
        df_seguridad = pd.DataFrame(datos_seg)

        # Crear Excel en buffer con las 8 pestañas completas
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_ventas.to_excel(writer, sheet_name='Ventas', index=False)
            df_abonos.to_excel(writer, sheet_name='Abonos', index=False)
            df_prods.to_excel(writer, sheet_name='Inventario', index=False)
            df_users.to_excel(writer, sheet_name='Usuarios', index=False)
            df_gastos.to_excel(writer, sheet_name='Gastos', index=False)
            df_catalogo.to_excel(writer, sheet_name='Catalogo_Productos', index=False)
            df_grupos.to_excel(writer, sheet_name='Grupos_Inventario', index=False)
            df_seguridad.to_excel(writer, sheet_name='Intentos_Seguridad', index=False)
            
        return output.getvalue()
    finally:
        session.close()

# Estado global compartido entre TODOS los usuarios en RAM de la app
_GLOBAL_BACKUP_STATE = {
    "last_date": None
}

def verificar_y_ejecutar_respaldo_diario(db):
    """
    Ejecuta el respaldo automático EXACTAMENTE 1 vez al día.
    Para sobrevivir a los reinicios de contenedor/RAM de Streamlit Cloud,
    consulta la tabla persistentemente en la base de datos (Supabase).
    """
    if "GDRIVE_WEBHOOK_URL" not in st.secrets and "gcp_service_account" not in st.secrets:
        return

    ahora_mx = get_mexico_time()
    fecha_hoy_str = ahora_mx.strftime('%Y-%m-%d')

    # 1. Chequeo rápido en memoria RAM de esta instancia
    if _GLOBAL_BACKUP_STATE.get("last_date") == fecha_hoy_str:
        return

    if st.session_state.get('respaldo_diario_fecha') == fecha_hoy_str:
        return

    # 2. Chequeo PERSISTENTE en la Base de Datos (Supabase)
    if hasattr(db, "get_session"):
        session = db.get_session()
    elif isinstance(db, tuple) and len(db) >= 2:
        session = db[1]()
    elif hasattr(db, "__call__"):
        session = db()
    else:
        from database import DatabaseHandler
        session = DatabaseHandler().get_session()

    try:
        from database import BitacoraRespaldo
        ya_respaldado = session.query(BitacoraRespaldo).filter_by(fecha_respaldo=fecha_hoy_str).first()
        if ya_respaldado:
            # Ya se ejecutó el respaldo hoy en la BD (por otra sesión o antes de reiniciar el contenedor)
            _GLOBAL_BACKUP_STATE["last_date"] = fecha_hoy_str
            st.session_state['respaldo_diario_fecha'] = fecha_hoy_str
            return
    except Exception as e_check:
        print(f"Advertencia consultando bitácora de respaldos: {e_check}")
    finally:
        session.close()

    # Si no existe en la base de datos para el día de hoy, bloquear temporalmente en RAM y ejecutar
    _GLOBAL_BACKUP_STATE["last_date"] = fecha_hoy_str
    st.session_state['respaldo_diario_fecha'] = fecha_hoy_str

    try:
        ok, msg = subir_respaldo_a_google_drive(db)
        if ok:
            # Registrar en la Base de Datos persistentemente
            if hasattr(db, "get_session"):
                s_log = db.get_session()
            elif isinstance(db, tuple) and len(db) >= 2:
                s_log = db[1]()
            elif hasattr(db, "__call__"):
                s_log = db()
            else:
                from database import DatabaseHandler
                s_log = DatabaseHandler().get_session()

            try:
                from database import BitacoraRespaldo
                nuevo_log = BitacoraRespaldo(fecha_respaldo=fecha_hoy_str, creado_el=ahora_mx)
                s_log.add(nuevo_log)
                s_log.commit()
            except Exception as e_save:
                s_log.rollback()
                print(f"Error registrando respaldo en BD: {e_save}")
            finally:
                s_log.close()

            st.toast(f"☁️ Respaldo automático diario a Google Drive realizado ({fecha_hoy_str})", icon="✅")
        else:
            # Si falló la subida, liberar la bandera para permitir reintento
            _GLOBAL_BACKUP_STATE["last_date"] = None
            st.session_state['respaldo_diario_fecha'] = None
    except Exception as e:
        _GLOBAL_BACKUP_STATE["last_date"] = None
        st.session_state['respaldo_diario_fecha'] = None
        print(f"Error en respaldo automático diario: {e}")


def subir_respaldo_a_google_drive(db):
    """
    Sube el archivo Excel generado a la carpeta de Google Drive.
    Soporta dos métodos:
    1. GDRIVE_WEBHOOK_URL (Google Apps Script Web App - Recomendado para cuentas personales sin límite de cuota)
    2. gcp_service_account (Service Account API)
    """
    if "GDRIVE_FOLDER_ID" not in st.secrets:
        return False, "No se encontró la variable GDRIVE_FOLDER_ID en Secrets."

    folder_id = st.secrets["GDRIVE_FOLDER_ID"].strip()
    excel_bytes = generar_excel_respaldo_completo(db)
    ahora = get_mexico_time()
    nombre_archivo = f"Respaldo_FB_Catalogo_{ahora.strftime('%Y-%m-%d_%H-%M')}.xlsx"

    # Método 1: Google Apps Script Webhook (Infalible para Drive Personal)
    if "GDRIVE_WEBHOOK_URL" in st.secrets and st.secrets["GDRIVE_WEBHOOK_URL"]:
        try:
            import base64
            import requests

            webhook_url = st.secrets["GDRIVE_WEBHOOK_URL"].strip()
            b64_data = base64.b64encode(excel_bytes).decode('utf-8')

            payload = {
                "folder_id": folder_id,
                "filename": nombre_archivo,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "data": b64_data
            }

            headers = {"Content-Type": "application/json"}
            res = requests.post(webhook_url, json=payload, headers=headers, timeout=60)

            # Si Apps Script devuelve JSON o HTML con exito
            if res.status_code == 200 and ("OK" in res.text or "success" in res.text.lower() or "id" in res.text.lower()):
                return True, f"✅ Respaldo '{nombre_archivo}' subido exitosamente a tu Google Drive."
            elif res.status_code in (200, 302) and not "DOCTYPE" in res.text:
                return True, f"✅ Respaldo '{nombre_archivo}' enviado correctamente a tu Google Drive."
            else:
                return False, f"Respuesta Webhook ({res.status_code}): {res.text[:150]}"
        except Exception as e_wh:
            return False, f"Error subiendo vía Webhook a Google Drive: {e_wh}"

    # Método 2: Service Account (Google Cloud API)
    if "gcp_service_account" not in st.secrets:
        return False, "No se encontró la configuración [gcp_service_account] ni GDRIVE_WEBHOOK_URL en Secrets."

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload

        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        scopes = ['https://www.googleapis.com/auth/drive.file', 'https://www.googleapis.com/auth/drive']
        credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {
            'name': nombre_archivo,
            'parents': [folder_id]
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(excel_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            resumable=True
        )

        archivo_subido = service.files().create(
            body=file_metadata,
            media_body=media,
            supportsAllDrives=True,
            fields='id, name, webViewLink'
        ).execute()

        return True, f"✅ Respaldo '{nombre_archivo}' subido exitosamente a Google Drive."
    except Exception as e:
        return False, f"Error subiendo respaldo a Google Drive: {e}"
