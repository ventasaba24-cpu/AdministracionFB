import io
import datetime
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

def get_mexico_time():
    return datetime.datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)

def generar_excel_respaldo_completo(db):
    """
    Genera un archivo Excel en memoria con 5 pestañas completas:
    - Ventas
    - Abonos
    - Inventarios
    - Usuarios
    - Gastos
    """
    session = db.get_session()
    try:
        from database import Venta, Abono, Producto, Usuario, Gasto
        
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
                "Comision_Cobrada": v.comision_cobrada
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
                "Metodo_Pago": a.metodo_pago
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

        # 4. Usuarios
        users = session.query(Usuario).all()
        datos_users = []
        for u in users:
            datos_users.append({
                "ID_Usuario": u.id,
                "Nombre": u.nombre,
                "Email": u.email,
                "Rol": u.rol,
                "Tasa_Comision": u.tasa_comision,
                "Patrocinador_Email": u.patrocinador_email,
                "Tipo_Vendedor": u.tipo_vendedor
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

        # Crear Excel en buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_ventas.to_excel(writer, sheet_name='Ventas', index=False)
            df_abonos.to_excel(writer, sheet_name='Abonos', index=False)
            df_prods.to_excel(writer, sheet_name='Inventario', index=False)
            df_users.to_excel(writer, sheet_name='Usuarios', index=False)
            df_gastos.to_excel(writer, sheet_name='Gastos', index=False)
            
        return output.getvalue()
    finally:
        session.close()

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
