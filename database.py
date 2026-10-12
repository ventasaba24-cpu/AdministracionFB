import os
import pandas as pd
import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, text, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

def get_mexico_time():
    return datetime.datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)

import unicodedata

def normalizar_texto(texto) -> str:
    """Normaliza texto eliminando acentos, diacríticos y convirtiendo a minúsculas para búsquedas insensibles a tildes."""
    if texto is None:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto).strip().lower())
        if unicodedata.category(c) != "Mn"
    )

def serie_contiene(serie: pd.Series, termino: str) -> pd.Series:
    """Retorna máscara booleana evaluando si la serie contiene el término ignorando acentos y mayúsculas."""
    if not termino:
        return pd.Series(True, index=serie.index)
    term_norm = normalizar_texto(termino)
    if not term_norm:
        return pd.Series(True, index=serie.index)
    return serie.fillna("").astype(str).map(normalizar_texto).str.contains(term_norm, regex=False, na=False)

Base = declarative_base()

# --- MODELOS DE DATOS ---

class GrupoInventario(Base):
    __tablename__ = 'grupos_inventario'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_grupo = Column(String(100), nullable=False)
    fecha_creacion = Column(DateTime, default=get_mexico_time)

class CatalogoProducto(Base):
    __tablename__ = 'catalogo_productos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), unique=True, nullable=False)
    categoria = Column(String(100), default='General')
    descripcion = Column(String(255), nullable=True)

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False) # Extendido a 255 para soportar Hashes
    rol = Column(String(50), default='Vendedor') # 'Admin' o 'Vendedor'
    tasa_comision = Column(Float, default=0.10) # 10% por defecto basado en los datos brindados
    patrocinador_email = Column(String(100), nullable=True) # Ligadura Multi-nivel
    tipo_vendedor = Column(String(50), default='Crédito') # 'Crédito' o 'One-Shot'
    session_token = Column(String(100), nullable=True) # UUID Session Key
    grupo_inventario_id = Column(Integer, ForeignKey('grupos_inventario.id', ondelete='SET NULL'), nullable=True)
    ultimo_login = Column(DateTime, nullable=True) # Fecha y hora del ultimo acceso registrado

class IntentoSeguridad(Base):
    __tablename__ = 'intentos_seguridad'
    id = Column(Integer, primary_key=True, autoincrement=True)
    identificador = Column(String(100), nullable=False, unique=True) # IP o Email atacado
    fallos = Column(Integer, default=0)
    bloqueado_hasta = Column(DateTime, nullable=True)
    ultimo_intento = Column(DateTime, default=get_mexico_time)

class BitacoraRespaldo(Base):
    __tablename__ = 'bitacora_respaldos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_respaldo = Column(String(20), nullable=False, unique=True) # 'YYYY-MM-DD'
    creado_el = Column(DateTime, default=get_mexico_time)

class BitacoraHomologacion(Base):
    __tablename__ = 'bitacora_homologaciones'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre_retirado = Column(String(150), nullable=False)
    nombre_oficial = Column(String(150), nullable=False)
    ventas_afectadas = Column(Integer, default=0)
    stock_trasladado = Column(Integer, default=0)
    fecha = Column(DateTime, default=get_mexico_time)


from sqlalchemy import UniqueConstraint

class Producto(Base):
    __tablename__ = 'productos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    vendedor_email = Column(String(100), ForeignKey('usuarios.email', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    stock = Column(Integer, default=0)
    precio = Column(Float, nullable=False)
    costo_compra = Column(Float, default=0.0) # Costo de inversión que solo ve el admin
    proveedor = Column(String(150), nullable=True) # Distribuidor/Proveedor que solo ve admin
    lote = Column(String(50), default='Lote 1')
    fecha_ingreso = Column(DateTime, default=get_mexico_time)
    
    __table_args__ = (UniqueConstraint('nombre', 'lote', 'vendedor_email', name='_nombre_lote_vendedor_uc'),)

class Venta(Base):
    __tablename__ = 'ventas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_venta = Column(DateTime, default=get_mexico_time)
    
    # Llaves foráneas
    vendedor_email = Column(String(100), ForeignKey('usuarios.email', onupdate='CASCADE', ondelete='CASCADE'))
    cliente = Column(String(150), nullable=False)
    producto_nombre = Column(String(150), nullable=False) # Guardamos el nombre del producto en el momento de la venta
    
    cantidad = Column(Integer, default=1)
    # Total Venta
    monto_total = Column(Float, nullable=False)
    
    # Costo base de la venta congelado (para soportar cambios de precios futuros sin arruinar la historia)
    costo_historico = Column(Float, default=0.0) 
    
    comision_cobrada = Column(Boolean, default=False) # Bandera que indica si el vendedor ya cobro los billetes físicos
    fecha_cobro_comision = Column(DateTime, nullable=True) # Momento exacto del retiro de la comisión
    
    # Relaciones
    abonos = relationship("Abono", back_populates="venta", cascade="all, delete-orphan")

class Abono(Base):
    __tablename__ = 'abonos'
    id_abono = Column(Integer, primary_key=True, autoincrement=True)
    venta_id = Column(Integer, ForeignKey('ventas.id'), nullable=False)
    fecha_abono = Column(DateTime, default=get_mexico_time)
    monto_abono = Column(Float, nullable=False)
    metodo_pago = Column(String(50), default="Tranferencia")
    
    # Campo opcional guardando texto o ubicación
    comprobante_foto = Column(String(255), nullable=True)
    
    venta = relationship("Venta", back_populates="abonos")

class Gasto(Base):
    __tablename__ = 'gastos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    concepto = Column(String(200), nullable=False)
    monto = Column(Float, nullable=False)
    categoria = Column(String(100), default="Otros")
    fecha_gasto = Column(DateTime, default=get_mexico_time)
    ticket_foto = Column(LargeBinary, nullable=True)
    factura_xml = Column(LargeBinary, nullable=True)
    factura_pdf = Column(LargeBinary, nullable=True)

# --- CONTROLADOR CENTRAL DE BASE DE DATOS ---

@st.cache_resource(show_spinner="Conectando base de datos...")
def init_db_connection(default_path='sqlite:///erp_database.db'):
    db_path = default_path
    try:
        db_url = None
        if "SUPABASE_URL" in st.secrets:
            db_url = st.secrets["SUPABASE_URL"]
        elif "DATABASE_URL" in st.secrets:
            db_url = st.secrets["DATABASE_URL"]
        else:
            # Buscar cualquier clave que contenga SUPABASE, POSTGRES o DATABASE ignorando mayúsculas
            for k in st.secrets.keys():
                if "SUPABASE" in str(k).upper() or "POSTGRES" in str(k).upper() or "DATABASE" in str(k).upper():
                    val = st.secrets[k]
                    if isinstance(val, str) and ("postgres" in val.lower() or "supabase" in val.lower()):
                        db_url = val
                        break

        if db_url:
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
                db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
            
            # Sanitizar URL mediante SQLAlchemy sin duplicar codificación percent-encode
            try:
                from sqlalchemy.engine.url import make_url
                u_obj = make_url(db_url)
                db_url = u_obj.render_as_string(hide_password=False)
            except Exception:
                pass
            db_path = db_url
    except Exception:
        pass
        
    print(f"🔌 Inicializando pool de conexiones: {'[NUBE PostgreSQL]' if 'postgresql' in db_path else '[LOCAL SQLite]'}")
    
    # Migración silenciosa de SQLite para no molestar al usuario con comandos manuales
    if "sqlite" in db_path:
        engine = create_engine(db_path, connect_args={"check_same_thread": False})
        Base.metadata.create_all(engine)
    else:
        try:
            # Entorno PostgreSQL (Nube Supabase)
            engine = create_engine(db_path, pool_pre_ping=True, pool_size=5, max_overflow=10)
            with engine.connect() as conn:
                for idx_sql in [
                    "CREATE INDEX IF NOT EXISTS idx_ventas_vendedor ON ventas(vendedor_email)",
                    "CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha_venta)",
                    "CREATE INDEX IF NOT EXISTS idx_ventas_producto ON ventas(producto_nombre)",
                    "CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre)",
                    "CREATE INDEX IF NOT EXISTS idx_abonos_venta ON abonos(venta_id)"
                ]:
                    try:
                        conn.execute(text(idx_sql))
                    except Exception:
                        pass
                conn.commit()
            Base.metadata.create_all(engine)
            try:
                if "db_conn_error" in st.session_state:
                    del st.session_state["db_conn_error"]
            except Exception:
                pass
        except Exception as e:
            print(f"⚠️ Fallo al conectar a PostgreSQL ({e}). Conectando a SQLite local de respaldo...")
            try:
                st.session_state["db_conn_error"] = str(e)
            except Exception:
                pass
            db_path = default_path
            engine = create_engine(db_path, connect_args={"check_same_thread": False})
            Base.metadata.create_all(engine)
    
    # Auto-migraciones para columnas añadidas en tablas pre-existentes (Compatibles con PostgreSQL y SQLite)
    columns_to_add = [
        ("usuarios", "patrocinador_email", "VARCHAR(100)"),
        ("usuarios", "tipo_vendedor", "VARCHAR(50) DEFAULT 'Crédito'"),
        ("usuarios", "session_token", "VARCHAR(100)"),
        ("usuarios", "grupo_inventario_id", "INTEGER"),
        ("usuarios", "ultimo_login", "TIMESTAMP"),
        ("productos", "costo_compra", "FLOAT DEFAULT 0.0"),
        ("productos", "proveedor", "VARCHAR(150) DEFAULT 'Generico'"),
        ("productos", "lote", "VARCHAR(50) DEFAULT 'Lote 1'"),
        ("productos", "fecha_ingreso", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ("ventas", "costo_historico", "FLOAT DEFAULT 0.0"),
        ("ventas", "comision_cobrada", "BOOLEAN DEFAULT FALSE"),
        ("ventas", "fecha_cobro_comision", "TIMESTAMP")
    ]

    for table_name, col_name, col_type in columns_to_add:
        try:
            with engine.connect() as conn:
                try:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                except Exception:
                    conn.rollback()
        except Exception:
            pass

    SessionMaker = sessionmaker(bind=engine, expire_on_commit=False)
    return engine, SessionMaker

def limpiar_cache_sistema():
    """Limpia la memoria caché de Streamlit para reflejar cambios en tiempo real."""
    try:
        st.cache_data.clear()
    except Exception:
        pass

_DEMO_INITIALIZED = False

@st.cache_data(ttl=180, show_spinner=False)
def _cached_leer_inventario(vendedor_email=None):
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        query = session.query(Producto)
        if vendedor_email:
            usr = session.query(Usuario).filter_by(email=vendedor_email).first()
            if usr and usr.grupo_inventario_id:
                miembros = [u.email for u in session.query(Usuario).filter_by(grupo_inventario_id=usr.grupo_inventario_id).all()]
                query = query.filter(Producto.vendedor_email.in_(miembros))
            else:
                query = query.filter_by(vendedor_email=vendedor_email)
        df = pd.read_sql(query.statement, session.bind)
        return df
    finally:
        session.close()

@st.cache_data(ttl=180, show_spinner=False)
def _cached_obtener_tabla_ventas_completa():
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        from sqlalchemy.orm import joinedload
        ventas = session.query(Venta).options(joinedload(Venta.abonos)).all()
        usuarios = session.query(Usuario).all()
        user_dict = {u.email: u for u in usuarios}
        
        productos = session.query(Producto).all()
        prod_dict = {}
        for p in productos:
            prod_dict[(p.nombre, p.vendedor_email)] = p
            if p.nombre not in prod_dict:
                prod_dict[p.nombre] = p
        
        datos_procesados = []
        for v in ventas:
            abonos_query = v.abonos
            total_abonos = sum([a.monto_abono for a in abonos_query]) if abonos_query else 0.0
            
            dias_ultimo = None
            if abonos_query:
                fechas_abono = [a.fecha_abono for a in abonos_query if a.fecha_abono]
                if fechas_abono:
                    ultimo = max(fechas_abono)
                    diferencia = get_mexico_time() - ultimo
                    dias_ultimo = diferencia.days
            
            if dias_ultimo is None:
                if v.fecha_venta:
                    dias_ultimo = (get_mexico_time() - v.fecha_venta).days
                else:
                    dias_ultimo = 0
            
            saldo = v.monto_total - total_abonos
            estado = "Pagado" if saldo <= 0 else "Adeudo"
            
            vendedor = user_dict.get(v.vendedor_email)
            tasa = vendedor.tasa_comision if vendedor else 0.10
            nombre_vendedor = vendedor.nombre if vendedor else "Desconocido"
            
            prod = prod_dict.get((v.producto_nombre, v.vendedor_email)) or prod_dict.get(v.producto_nombre)
            nombre_proveedor = prod.proveedor if prod and prod.proveedor else "Desconocido"
            
            comision_ganada = v.monto_total * tasa
            comision_pagada = "SI" if estado == "Pagado" else "NO"
            
            subtotal_sin_iva = v.monto_total / 1.16
            iva_generado = v.monto_total - subtotal_sin_iva
            
            # costo_historico ya representa el costo total de la venta (piezas x costo)
            costo_bases = float(getattr(v, "costo_historico", 0.0) or 0.0)
            cant = int(getattr(v, "cantidad", 1) or 1)
            costo_unit = (costo_bases / cant) if cant > 0 else 0.0
            
            utilidad_neta = subtotal_sin_iva - costo_bases - comision_ganada
            
            fila = {
                "ID_Venta": v.id,
                "Fecha_Venta": v.fecha_venta.strftime("%d-%b-%Y") if v.fecha_venta else "",
                "Dias_Ultimo_Abono": dias_ultimo,
                "Nombre_Vendedor": nombre_vendedor,
                "Vendedor_Email": v.vendedor_email,
                "Cliente": v.cliente,
                "Producto": v.producto_nombre,
                "Cantidad": cant,
                "Proveedor": nombre_proveedor,
                "Total_Venta": v.monto_total,
                "IVA_(16%)": iva_generado,
                "Costo_Producto": costo_bases,
                "Total_Abono": total_abonos,
                "Saldo_Pendiente": saldo,
                "Estado_Venta": estado,
                "Comision_Generada": comision_ganada,
                "Utilidad_Neta": utilidad_neta,
                "Comision_Pagada": comision_pagada,
                "Comision_Fisicamente_Cobrada": v.comision_cobrada,
                "Fecha_Cobro_Comision": v.fecha_cobro_comision.strftime("%d-%b-%Y") if hasattr(v, "fecha_cobro_comision") and v.fecha_cobro_comision else ""
            }
            datos_procesados.append(fila)
            
        return pd.DataFrame(datos_procesados)
    finally:
        session.close()

@st.cache_data(ttl=180, show_spinner=False)
def _cached_leer_abonos():
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        query = session.query(Abono)
        df = pd.read_sql(query.statement, session.bind)
        return df
    finally:
        session.close()

@st.cache_data(ttl=180, show_spinner=False)
def _cached_obtener_vendedores():
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        query = session.query(Usuario).filter(Usuario.rol != "Admin")
        df = pd.read_sql(query.statement, session.bind)
        return df
    finally:
        session.close()

@st.cache_data(ttl=180, show_spinner=False)
def _cached_obtener_gastos():
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        gastos = session.query(
            Gasto.id,
            Gasto.concepto,
            Gasto.monto,
            Gasto.categoria,
            Gasto.fecha_gasto,
            (Gasto.ticket_foto != None).label('tiene_foto'),
            (Gasto.factura_xml != None).label('tiene_xml'),
            (Gasto.factura_pdf != None).label('tiene_pdf')
        ).order_by(Gasto.fecha_gasto.desc()).all()
        data = []
        for g in gastos:
            data.append({
                "ID": g.id,
                "Concepto": g.concepto,
                "Monto": g.monto,
                "Categoria": g.categoria,
                "Fecha": g.fecha_gasto.strftime("%d-%m-%Y %H:%M") if g.fecha_gasto else "",
                "Tiene_Foto": bool(g.tiene_foto),
                "Foto_Bytes": None,
                "Tiene_XML": bool(g.tiene_xml),
                "Tiene_PDF": bool(g.tiene_pdf),
                "XML_Bytes": None,
                "PDF_Bytes": None
            })
        return pd.DataFrame(data)
    finally:
        session.close()

@st.cache_data(ttl=180, show_spinner=False)
def _cached_obtener_catalogo_maestro():
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        prods = session.query(CatalogoProducto).order_by(CatalogoProducto.nombre.asc()).all()
        if not prods:
            nombres_existentes = session.query(Producto.nombre).distinct().all()
            for (nom,) in nombres_existentes:
                if nom and nom.strip():
                    c_p = CatalogoProducto(nombre=nom.strip(), categoria="General")
                    session.add(c_p)
            session.commit()
            prods = session.query(CatalogoProducto).order_by(CatalogoProducto.nombre.asc()).all()
        return [{"id": p.id, "nombre": p.nombre, "categoria": p.categoria, "descripcion": p.descripcion} for p in prods]
    finally:
        session.close()

@st.cache_data(ttl=180, show_spinner=False)
def _cached_obtener_grupos_inventario():
    _, SessionMaker = init_db_connection()
    session = SessionMaker()
    try:
        grupos = session.query(GrupoInventario).all()
        resultado = []
        for g in grupos:
            miembros = session.query(Usuario).filter_by(grupo_inventario_id=g.id).all()
            resultado.append({
                "id": g.id,
                "nombre_grupo": g.nombre_grupo,
                "fecha_creacion": g.fecha_creacion,
                "miembros": [{"email": m.email, "nombre": m.nombre} for m in miembros]
            })
        return resultado
    finally:
        session.close()

class DatabaseHandler:
    def __init__(self):
        # Reutiliza el Pool de Conexión global guardado en RAM por Streamlit
        self.engine, self.Session = init_db_connection()
        global _DEMO_INITIALIZED
        if not _DEMO_INITIALIZED:
            self.inicializar_datos_demo()
            _DEMO_INITIALIZED = True

    def get_session(self):
        return self.Session()
    
    def inicializar_datos_demo(self):
        """Inyecta un usuario administrador de forma automática si la tabla está vacía."""
        session = self.get_session()
        try:
            admin_existe = session.query(Usuario).filter_by(rol="Admin").first()
            if not admin_existe:
                admin_user = Usuario(
                    nombre="Administrador Principal",
                    email="admin@empresa.com",
                    password=generate_password_hash("admin", method="pbkdf2:sha256"),
                    rol="Admin",
                    tasa_comision=0.0
                )
                session.add(admin_user)
                session.commit()
                print("⚙️ Usuario Administrador inicializado.")
                
            demo_existe = session.query(Usuario).filter_by(email="vendedor@demo.com").first()
            if not demo_existe:
                vendedor_user = Usuario(
                    nombre="Vendedor de Demo",
                    email="vendedor@demo.com",
                    password=generate_password_hash("123", method="pbkdf2:sha256"),
                    rol="Vendedor",
                    tasa_comision=0.10
                )
                session.add(vendedor_user)
                session.commit()
                print("⚙️ Usuario Vendedor de demostración inicializado.")

        finally:
            session.close()

    # ==========================
    #   OPERACIONES INVENTARIO
    # ==========================
    
    def leer_inventario(self, vendedor_email=None):
        """Devuelve el inventario en formato DataFrame de Pandas. Si no se provee email, devuelve todos. Si el vendedor pertenece a un grupo de inventario compartido, incluye el stock del grupo."""
        return _cached_leer_inventario(vendedor_email=vendedor_email)

    def obtener_valor_inventario(self):
        """Calcula el capital físico actual sumando (stock * costo_compra) de todos los productos."""
        session = self.get_session()
        try:
            total_valor = 0.0
            productos = session.query(Producto).all()
            for p in productos:
                total_valor += (p.stock * p.costo_compra)
            return total_valor
        finally:
            session.close()

    def asegurar_en_catalogo(self, session, nombre_producto):
        """Garantiza que el nombre del producto exista en el catálogo maestro."""
        nombre_clean = str(nombre_producto).strip()
        if not nombre_clean:
            return
        existente = session.query(CatalogoProducto).filter(func.lower(CatalogoProducto.nombre) == nombre_clean.lower()).first()
        if not existente:
            nuevo = CatalogoProducto(nombre=nombre_clean, categoria="General")
            session.add(nuevo)

    def guardar_inventario(self, df_inventario, vendedor_email):
        """Sobreescribe el inventario de un vendedor específico basado en el DataFrame del UI."""
        session = self.get_session()
        try:
            # Respaldar los costos de compra, proveedores y fechas de ingreso actuales
            old_products = session.query(Producto).filter_by(vendedor_email=vendedor_email).all()
            costos_map = {f"{p.nombre}-{p.lote}": p.costo_compra for p in old_products}
            provs_map = {f"{p.nombre}-{p.lote}": p.proveedor for p in old_products}
            fechas_map = {f"{p.nombre}-{p.lote}": p.fecha_ingreso for p in old_products}
            
            # Borramos el previo stock de este vendedor
            session.query(Producto).filter_by(vendedor_email=vendedor_email).delete(synchronize_session=False)
            
            # Precargar catálogo maestro en memoria para evitar N consultas individuales a la red
            cat_existentes = {c.nombre.strip().lower() for c in session.query(CatalogoProducto.nombre).all() if c.nombre}
            
            for index, row in df_inventario.iterrows():
                # Ignorar filas vacías
                nombre = str(row.get('nombre', '')).strip()
                if not nombre or pd.isna(row.get('nombre')):
                    continue
                    
                lote = row.get('lote', 'Lote 1')
                if pd.isna(lote) or not str(lote).strip():
                    lote = 'Lote 1'
                lote = str(lote).strip()
                key_map = f"{nombre}-{lote}"
                    
                # Si el df trae "costo_compra" (Admin), úsalo. Si no (Vendedor), rescata el viejo (o 0.0).
                costo_nuevo = row.get('costo_compra')
                if pd.isna(costo_nuevo) or costo_nuevo is None:
                    costo_nuevo = costos_map.get(key_map, 0.0)
                    
                prov_nuevo = row.get('proveedor')
                if pd.isna(prov_nuevo) or prov_nuevo is None:
                    prov_nuevo = provs_map.get(key_map, "Desconocido")

                fecha_ing = row.get('fecha_ingreso')
                if pd.isna(fecha_ing) or fecha_ing is None:
                    fecha_ing = fechas_map.get(key_map, get_mexico_time())
                    
                nuevo_prod = Producto(
                    nombre=nombre,
                    vendedor_email=vendedor_email,
                    stock=int(row.get('stock', 0)),
                    precio=float(row.get('precio', 0.0)),
                    costo_compra=float(costo_nuevo),
                    proveedor=str(prov_nuevo),
                    lote=lote,
                    fecha_ingreso=fecha_ing
                )
                session.add(nuevo_prod)
                
                # Inserción rápida en catálogo maestro en memoria si no existía
                if nombre.lower() not in cat_existentes:
                    session.add(CatalogoProducto(nombre=nombre, categoria="General"))
                    cat_existentes.add(nombre.lower())

            session.commit()
            limpiar_cache_sistema()
            return True, "Inventario sincronizado."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    @staticmethod
    def calcular_siguiente_lote(lotes_existentes):
        """Calcula de forma segura el siguiente identificador de lote consecutivo."""
        import re
        if not lotes_existentes:
            return "Lote 1"
        numeros = []
        for l in lotes_existentes:
            if not l:
                continue
            nums = re.findall(r'\d+', str(l))
            if nums:
                try:
                    numeros.append(int(nums[-1]))
                except ValueError:
                    pass
        if not numeros:
            return f"Lote {len(lotes_existentes) + 1}"
        return f"Lote {max(numeros) + 1}"

    def obtener_lotes_producto_vendedor(self, nombre_producto, vendedor_email):
        """Devuelve los lotes registrados de un producto específico para un vendedor."""
        session = self.get_session()
        try:
            nombre_clean = str(nombre_producto).strip()
            prods = session.query(Producto).filter(
                or_(
                    Producto.nombre == nombre_clean,
                    func.trim(func.lower(Producto.nombre)) == nombre_clean.lower()
                ),
                Producto.vendedor_email == vendedor_email
            ).order_by(Producto.id.asc()).all()
            return [
                {
                    "id": p.id,
                    "nombre": p.nombre,
                    "lote": p.lote or "Lote 1",
                    "stock": p.stock or 0,
                    "precio": p.precio or 0.0,
                    "costo_compra": p.costo_compra or 0.0,
                    "proveedor": p.proveedor or "Generico",
                    "fecha_ingreso": p.fecha_ingreso
                }
                for p in prods
            ]
        finally:
            session.close()

    def upsert_producto(self, vendedor_email, datos, producto_id=None):
        session = self.get_session()
        try:
            nombre_val = str(datos["nombre"]).strip()
            lote_val = str(datos.get("lote", "Lote 1")).strip()
            
            # Validación anticolisión de lote para este vendedor
            existente_mismo_lote = session.query(Producto).filter(
                func.trim(func.lower(Producto.nombre)) == nombre_val.lower(),
                func.trim(func.lower(Producto.lote)) == lote_val.lower(),
                Producto.vendedor_email == vendedor_email
            ).first()
            if existente_mismo_lote and (producto_id is None or existente_mismo_lote.id != producto_id):
                return False, f"⚠️ Ya existe el '{lote_val}' registrado para '{nombre_val}' en esta bodega. Utiliza un lote diferente para evitar duplicados."

            f_val = datos.get("fecha_ingreso")
            if f_val:
                if isinstance(f_val, str):
                    try:
                        f_val = datetime.datetime.fromisoformat(f_val)
                    except:
                        f_val = get_mexico_time()
                elif isinstance(f_val, datetime.date) and not isinstance(f_val, datetime.datetime):
                    f_val = datetime.datetime.combine(f_val, datetime.time.min)
            else:
                f_val = get_mexico_time()

            if producto_id:
                prod = session.query(Producto).filter_by(id=producto_id, vendedor_email=vendedor_email).first()
                if not prod:
                    return False, "Producto no encontrado."
                prod.nombre = nombre_val
                prod.lote = lote_val
                prod.precio = float(datos.get("precio", 0.0))
                prod.costo_compra = float(datos.get("costo_compra", 0.0))
                prod.proveedor = str(datos.get("proveedor", "Generico")).strip()
                prod.stock = int(datos.get("stock", 0))
                prod.fecha_ingreso = f_val
            else:
                prod = Producto(
                    nombre=nombre_val,
                    vendedor_email=vendedor_email,
                    lote=lote_val,
                    precio=float(datos.get("precio", 0.0)),
                    costo_compra=float(datos.get("costo_compra", 0.0)),
                    proveedor=str(datos.get("proveedor", "Generico")).strip(),
                    stock=int(datos.get("stock", 0)),
                    fecha_ingreso=f_val
                )
                session.add(prod)
            self.asegurar_en_catalogo(session, nombre_val)
            session.commit()
            limpiar_cache_sistema()
            return True, "Producto guardado satisfactoriamente."
        except Exception as e:
            session.rollback()
            return False, f"Error: {e}"
        finally:
            session.close()

    def eliminar_inventario_producto(self, producto_id, vendedor_email):
        session = self.get_session()
        try:
            prod = session.query(Producto).filter_by(id=producto_id, vendedor_email=vendedor_email).first()
            if prod:
                session.delete(prod)
                session.commit()
                limpiar_cache_sistema()
                return True, "Producto eliminado."
            return False, "Producto no encontrado."
        except Exception as e:
            session.rollback()
            return False, f"Error al eliminar: {e}"
        finally:
            session.close()

    def actualizar_stock(self, producto_nombre, cantidad_vendida, vendedor_email):
        session = self.get_session()
        try:
            usr = session.query(Usuario).filter_by(email=vendedor_email).first()
            if usr and usr.grupo_inventario_id:
                miembros = [u.email for u in session.query(Usuario).filter_by(grupo_inventario_id=usr.grupo_inventario_id).all()]
            else:
                miembros = [vendedor_email]

            productos_lotes = session.query(Producto).filter(
                Producto.nombre == producto_nombre,
                Producto.vendedor_email.in_(miembros)
            ).filter(Producto.stock > 0).order_by(Producto.fecha_ingreso.asc(), Producto.id.asc()).all()

            if not productos_lotes:
                return False
                
            restante = cantidad_vendida
            for p in productos_lotes:
                if restante <= 0:
                    break
                if p.stock >= restante:
                    p.stock -= restante
                    restante = 0
                else:
                    restante -= p.stock
                    p.stock = 0
            session.commit()
            return True
        finally:
            session.close()

    # ==========================
    #   OPERACIONES VENTAS Y ABONOS (CON LÓGICA DE NEGOCIO PANDAS)
    # ==========================
    
    def registrar_venta(self, vendedor_email, cliente, producto, cantidad, precio_unitario):
        session = self.get_session()
        try:
            monto_total = float(cantidad) * float(precio_unitario)
            
            usr = session.query(Usuario).filter_by(email=vendedor_email).first()
            if usr and usr.grupo_inventario_id:
                miembros_emails = [u.email for u in session.query(Usuario).filter_by(grupo_inventario_id=usr.grupo_inventario_id).all()]
            else:
                miembros_emails = [vendedor_email]

            # FIFO Logic ordenado por fecha_ingreso y Candado de Concurrencia
            try:
                productos_lotes = session.query(Producto).filter(
                    Producto.nombre == producto,
                    Producto.vendedor_email.in_(miembros_emails)
                ).with_for_update().order_by(Producto.fecha_ingreso.asc(), Producto.id.asc()).all()
            except Exception:
                session.rollback()
                productos_lotes = session.query(Producto).filter(
                    Producto.nombre == producto,
                    Producto.vendedor_email.in_(miembros_emails)
                ).order_by(Producto.fecha_ingreso.asc(), Producto.id.asc()).all()
            
            restante_a_descontar = cantidad
            costo_total = 0.0
            
            if not productos_lotes:
                costo_total = 0.0
            else:
                for mi_producto in productos_lotes:
                    if restante_a_descontar <= 0:
                        break
                    
                    if mi_producto.stock > 0:
                        if mi_producto.stock >= restante_a_descontar:
                            costo_total += float(restante_a_descontar) * mi_producto.costo_compra
                            mi_producto.stock -= restante_a_descontar
                            restante_a_descontar = 0
                        else:
                            costo_total += float(mi_producto.stock) * mi_producto.costo_compra
                            restante_a_descontar -= mi_producto.stock
                            mi_producto.stock = 0
                            
                # Si vendimos más unidades de las registradas en stock físico, cobramos el sobrante con el costo del lote más reciente
                if restante_a_descontar > 0:
                    last_cost = productos_lotes[-1].costo_compra
                    costo_total += float(restante_a_descontar) * last_cost
            
            nueva_venta = Venta(
                vendedor_email=vendedor_email,
                cliente=cliente,
                producto_nombre=producto,
                cantidad=cantidad,
                monto_total=monto_total,
                costo_historico=costo_total, # Congelado para la historia de utilidades de los lotes exactos
                fecha_venta=get_mexico_time()
            )
            session.add(nueva_venta)
            session.commit()
            limpiar_cache_sistema()
            return True, nueva_venta.id, monto_total
        except Exception as e:
            session.rollback()
            print(f"Error al registrar venta: {e}")
            return False, None, 0.0
        finally:
            session.close()

    def corregir_costo_y_nombre_venta(self, id_venta, nuevo_costo_unitario, nuevo_nombre_producto):
        """Corrige el costo histórico y el nombre de una venta, y (si no existe) registra el producto para su proveedor."""
        session = self.get_session()
        try:
            venta = session.query(Venta).filter_by(id=id_venta).first()
            if not venta:
                return False, "ID de Venta no encontrada."
            
            # Actualizar nombre y recalcular costo
            venta.producto_nombre = nuevo_nombre_producto
            venta.costo_historico = float(venta.cantidad) * float(nuevo_costo_unitario)
            
            # Verificar si el producto ya existe en la base con el nombre final
            prod = session.query(Producto).filter_by(nombre=nuevo_nombre_producto, vendedor_email=venta.vendedor_email).first()
            
            if prod:
                # Si existe, quizá era un costo 0, lo corregimos
                if prod.costo_compra == 0.0:
                    prod.costo_compra = float(nuevo_costo_unitario)
            else:
                # Si no existía lo agregamos al catálogo
                precio_unitario_venta = venta.monto_total / float(venta.cantidad) if float(venta.cantidad) > 0 else venta.monto_total
                nuevo_prod = Producto(
                    nombre=nuevo_nombre_producto,
                    precio=precio_unitario_venta, # Usamos de sugerencia al precio al que lo acaba de vender
                    costo_compra=float(nuevo_costo_unitario),
                    vendedor_email=venta.vendedor_email,
                    proveedor="Generico (Autoguardado)",
                    stock=0 # 0 porque ya se vendió, solo existe para registrar historial
                )
                session.add(nuevo_prod)
                
            session.commit()
            limpiar_cache_sistema()
            return True, "Costo y Nombre corregidos satisfactoriamente."
        except Exception as e:
            session.rollback()
            return False, f"Error: {str(e)}"
        finally:
            session.close()

    def registrar_abono(self, venta_id, monto, metodo="Efectivo", fecha_abono=None):
        session = self.get_session()
        if fecha_abono is None:
            fecha_abono = get_mexico_time()
        
        try:
            venta_existe = session.query(Venta).filter_by(id=venta_id).first()
            if not venta_existe:
                return False, "Esa ID de Venta no existe."
                
            nuevo_abono = Abono(
                venta_id=venta_id,
                monto_abono=monto,
                fecha_abono=fecha_abono,
                metodo_pago=metodo
            )
            session.add(nuevo_abono)
            session.commit()
            limpiar_cache_sistema()
            return True, "Abono registrado con éxito."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def leer_abonos_por_venta(self, venta_id):
        session = self.get_session()
        try:
            return session.query(Abono).filter_by(venta_id=venta_id).order_by(Abono.fecha_abono.asc()).all()
        finally:
            session.close()

    def marcar_comision_cobrada(self, venta_id):
        session = self.get_session()
        try:
             venta = session.query(Venta).filter_by(id=venta_id).first()
             if venta:
                  venta.comision_cobrada = True
                  venta.fecha_cobro_comision = get_mexico_time()
                  session.commit()
                  limpiar_cache_sistema()
                  return True, "Se ha registrado el cobro de esta comisión."
             return False, "Venta no encontrada."
        except Exception as e:
             session.rollback()
             return False, str(e)
        finally:
             session.close()

    def obtener_tabla_ventas_completa(self):
        """
        Calcula dinámicamente el DataFrame enlazando Ventas + Abonos y generando Estados.
        (Optimizado para evitar el problema de N+1 queries en la Nube - Modelo Venta Directa)
        """
        return _cached_obtener_tabla_ventas_completa()

    def _devolver_stock(self, session, vendedor_email, producto_nombre, cantidad):
        """Devuelve stock al inventario considerando grupos de inventario compartido o restituyendo el producto."""
        if cantidad <= 0 or not producto_nombre:
            return
        
        usr = session.query(Usuario).filter_by(email=vendedor_email).first()
        miembros = [vendedor_email]
        if usr and usr.grupo_inventario_id:
            miembros = [u.email for u in session.query(Usuario).filter_by(grupo_inventario_id=usr.grupo_inventario_id).all()]
            
        prod = session.query(Producto).filter(
            Producto.nombre == producto_nombre,
            Producto.vendedor_email.in_(miembros)
        ).order_by(Producto.fecha_ingreso.desc(), Producto.id.desc()).first()
        
        if prod:
            prod.stock += cantidad
        else:
            nuevo_p = Producto(
                nombre=producto_nombre,
                vendedor_email=vendedor_email,
                stock=cantidad,
                precio=0.0,
                costo_compra=0.0,
                proveedor="Restauración Corrección",
                lote="Lote 1",
                fecha_ingreso=get_mexico_time()
            )
            session.add(nuevo_p)
            self.asegurar_en_catalogo(session, producto_nombre)

    def _descontar_stock(self, session, vendedor_email, producto_nombre, cantidad):
        """Descuenta stock del inventario considerando grupos compartidos."""
        if cantidad <= 0 or not producto_nombre:
            return
            
        usr = session.query(Usuario).filter_by(email=vendedor_email).first()
        miembros = [vendedor_email]
        if usr and usr.grupo_inventario_id:
            miembros = [u.email for u in session.query(Usuario).filter_by(grupo_inventario_id=usr.grupo_inventario_id).all()]
            
        prods = session.query(Producto).filter(
            Producto.nombre == producto_nombre,
            Producto.vendedor_email.in_(miembros)
        ).filter(Producto.stock > 0).order_by(Producto.fecha_ingreso.asc(), Producto.id.asc()).all()
        
        restante = cantidad
        for p in prods:
            if restante <= 0:
                break
            if p.stock >= restante:
                p.stock -= restante
                restante = 0
            else:
                restante -= p.stock
                p.stock = 0

    def eliminar_venta(self, venta_id):
        session = self.get_session()
        try:
            venta = session.query(Venta).filter_by(id=venta_id).first()
            if not venta:
                return False, "Venta no encontrada."
            
            # Devolver stock siempre considerando grupo compartido
            self._devolver_stock(session, venta.vendedor_email, venta.producto_nombre, venta.cantidad)
                
            # Logica Anti-fugas
            if venta.comision_cobrada:
                session.query(Abono).filter_by(venta_id=venta_id).delete()
                venta.estado = 'Devolución/Cancelada (Reversa)'
                venta.monto_total = 0.0
                venta.cantidad = 0
                venta.costo_historico = 0.0
                venta.comision_generada = -abs(venta.comision_generada) if venta.comision_generada else 0.0
                if hasattr(venta, 'comision_red') and venta.comision_red:
                    venta.comision_red = -abs(venta.comision_red)
                session.commit()
                limpiar_cache_sistema()
                return True, "Venta anulada. Ya se le había pagado comisión; se pasmó en monto negativo para ser restada de su próximo pago."
            else:
                session.delete(venta) # Cascada eliminará Abonos adjuntos
                session.commit()
                limpiar_cache_sistema()
                return True, "Venta eliminada exitosamente y stock devuelto."
        except Exception as e:
            session.rollback()
            return False, f"Error al eliminar venta: {e}"
        finally:
            session.close()

    def editar_venta_completa(self, venta_id, nuevo_cliente, nuevo_producto, nueva_cantidad, nuevo_monto, nuevo_costo_proveedor):
        session = self.get_session()
        try:
            venta = session.query(Venta).filter_by(id=venta_id).first()
            if not venta:
                return False, "Venta no encontrada."
                
            cantidad_int = int(nueva_cantidad)
            monto_float = float(nuevo_monto)
            costo_float = float(nuevo_costo_proveedor)
            
            # Si el producto o la cantidad cambió, ajustamos el stock considerando grupos compartidos
            if venta.producto_nombre != nuevo_producto or venta.cantidad != cantidad_int:
                # 1. Devolver el producto viejo al inventario del grupo
                self._devolver_stock(session, venta.vendedor_email, venta.producto_nombre, venta.cantidad)
                
                # 2. Descontar el producto nuevo del inventario del grupo
                self._descontar_stock(session, venta.vendedor_email, nuevo_producto, cantidad_int)
                    
            venta.cliente = nuevo_cliente
            venta.producto_nombre = nuevo_producto
            venta.cantidad = cantidad_int
            venta.monto_total = monto_float
            venta.costo_historico = costo_float
            
            session.commit()
            limpiar_cache_sistema()
            return True, "Registro actualizado en sistema y control de inventario."
        except Exception as e:
            session.rollback()
            return False, f"Error al editar venta: {e}"
        finally:
            session.close()

    def eliminar_abono(self, abono_id):
        session = self.get_session()
        try:
            abono = session.query(Abono).filter_by(id_abono=abono_id).first()
            if not abono:
                return False, "Abono no encontrado."
                
            session.delete(abono)
            session.commit()
            limpiar_cache_sistema()
            return True, "Abono cancelado exitosamente."
        except Exception as e:
            session.rollback()
            return False, f"Error al eliminar abono: {e}"
        finally:
            session.close()
            
    def editar_abono(self, abono_id, nuevo_monto, nuevo_metodo):
        session = self.get_session()
        try:
            abono = session.query(Abono).filter_by(id_abono=abono_id).first()
            if not abono:
                return False, "Abono no encontrado."
                
            abono.monto_abono = float(nuevo_monto)
            abono.metodo_pago = nuevo_metodo
            session.commit()
            limpiar_cache_sistema()
            return True, "Recibo actualizado correctamente."
        except Exception as e:
            session.rollback()
            return False, f"Error al actualizar abono: {e}"
        finally:
            session.close()

    def leer_abonos(self):
        return _cached_leer_abonos()

    # ==========================
    #   USUARIOS Y AUTENTICACIÓN LOGIC PÚBLICA
    # ==========================
    
    def verificar_y_registrar_intento(self, session, identificador):
        """Verifica si un identificador (IP o Email) está bloqueado por demasiados intentos. Si no, lo deja pasar (True), si sí, devuelve (False)"""
        registro = session.query(IntentoSeguridad).filter_by(identificador=identificador).first()
        if not registro:
            return True, None # No hay registro, puede intentar
            
        if registro.bloqueado_hasta and registro.bloqueado_hasta > get_mexico_time():
            return False, registro.bloqueado_hasta # Está bloqueado
            
        return True, None

    def registrar_fallo(self, session, identificador):
        """Suma un fallo a este identificador. Bloquea si llega a 3."""
        registro = session.query(IntentoSeguridad).filter_by(identificador=identificador).first()
        if not registro:
            registro = IntentoSeguridad(identificador=identificador, fallos=1)
            session.add(registro)
        else:
            # Si ya pasó su tiempo de bloqueo antiguo, resetear fallos
            if registro.bloqueado_hasta and registro.bloqueado_hasta <= get_mexico_time():
                 registro.fallos = 1
                 registro.bloqueado_hasta = None
            else:
                 registro.fallos += 1
            
            if registro.fallos >= 3:
                # Bloquear por 15 minutos
                registro.bloqueado_hasta = get_mexico_time() + datetime.timedelta(minutes=15)
        
        registro.ultimo_intento = get_mexico_time()
        session.commit()

    def limpiar_fallos(self, session, identificador):
        """Limpia el historial de fallos cuando el usuario acierta la contraseña."""
        registro = session.query(IntentoSeguridad).filter_by(identificador=identificador).first()
        if registro:
             registro.fallos = 0
             registro.bloqueado_hasta = None
             session.commit()

    def login_seguro(self, email, password, ip_address):
        session = self.get_session()
        try:
             # Generar un identificador de seguridad híbrido (Por IP si existe, sino por EMAIL como fallback)
             # Preferimos IP real_ip para bloquear atacantes masivos, o el correo atacado directamente
             id_seguridad = ip_address if ip_address else email
             
             permitido, tiempo_bloqueo = self.verificar_y_registrar_intento(session, id_seguridad)
             if not permitido:
                 # Restar minutos locales
                 resta = tiempo_bloqueo - get_mexico_time()
                 minutos_restantes = max(1, int(resta.total_seconds() / 60))
                 return False, None, None, f"Por seguridad tecnológica, este acceso ha sido temporalmente suspendido. Intente de nuevo en {minutos_restantes} minutos."
             
             # Buscar existencial (case-insensitive e ignorando espacios accidentales al escribir)
             from sqlalchemy import func
             usr = session.query(Usuario).filter(func.lower(Usuario.email) == func.lower(str(email).strip())).first()
             
             # Fallo intencional temprano si no existe el correo
             if not usr:
                 self.registrar_fallo(session, id_seguridad)
                 return False, None, None, "Credenciales inválidas."
                 
             # Validar el hash o texto plano
             es_valido = False
             if usr.password == password:
                 es_valido = True
                 try:
                     usr.password = generate_password_hash(password, method="pbkdf2:sha256")
                     session.commit()
                 except Exception:
                     session.rollback()
             else:
                 try:
                     es_valido = check_password_hash(usr.password, password)
                 except Exception:
                     es_valido = False

             if not es_valido:
                 self.registrar_fallo(session, id_seguridad)
                 return False, None, None, "Credenciales inválidas."
             
             # Si llegó aquí, todo está bien
             import uuid
             nuevo_token = str(uuid.uuid4())
             usr.session_token = nuevo_token
             usr.ultimo_login = get_mexico_time()
             session.commit()
             
             self.limpiar_fallos(session, id_seguridad)
             return True, usr, nuevo_token, "OK"
        except Exception as e:
             session.rollback()
             return False, None, None, "Error interno de validación"
        finally:
             session.close()

    def get_user_by_email(self, email):
        session = self.get_session()
        try:
             usr = session.query(Usuario).filter_by(email=email).first()
             return usr
        finally:
             session.close()

    def get_user_by_token(self, token):
        session = self.get_session()
        try:
             usr = session.query(Usuario).filter_by(session_token=token).first()
             if usr:
                 try:
                     usr.ultimo_login = get_mexico_time()
                     session.commit()
                 except Exception:
                     session.rollback()
             return usr
        finally:
             session.close()
             
    def limpiar_sesion_token(self, token):
        session = self.get_session()
        try:
             usr = session.query(Usuario).filter_by(session_token=token).first()
             if usr:
                 usr.session_token = None
                 session.commit()
        finally:
             session.close()

    def obtener_vendedores(self):
        return _cached_obtener_vendedores()

    def registrar_vendedor(self, nombre, email, password, comision=0.10, patrocinador_email=None, tipo_vendedor="Crédito"):
        session = self.get_session()
        try:
            nuevo = Usuario(
                nombre=nombre,
                email=email,
                password=generate_password_hash(password, method="pbkdf2:sha256"),
                rol="Vendedor",
                tasa_comision=comision/100.0, # Guardar directo como tasa decimal (10% -> 0.10)
                patrocinador_email=patrocinador_email,
                tipo_vendedor=tipo_vendedor
            )
            session.add(nuevo)
            session.commit()
            limpiar_cache_sistema()
            return True, "Vendedor registrado correctamente."
        except IntegrityError:
            session.rollback()
            return False, "El correo ya está registrado."
        except Exception as e:
            session.rollback()
            return False, f"Error desconocido: {e}"
        finally:
            session.close()

    def leer_metricas_red(self, patrocinador_email):
        """Calcula el rendimiento multinivel de 3 generaciones."""
        session = self.get_session()
        try:
            niveles = {
                1: {"comision": 0.05, "usuarios": [], "bono": 0.0},
                2: {"comision": 0.03, "usuarios": [], "bono": 0.0},
                3: {"comision": 0.02, "usuarios": [], "bono": 0.0}
            }
            
            # Nivel 1
            n1 = session.query(Usuario).filter_by(patrocinador_email=patrocinador_email).all()
            if n1: niveles[1]["usuarios"] = n1
            
            # Nivel 2
            if n1:
                n1_emails = [u.email for u in n1]
                n2 = session.query(Usuario).filter(Usuario.patrocinador_email.in_(n1_emails)).all()
                if n2: niveles[2]["usuarios"] = n2
                
                # Nivel 3
                if n2:
                    n2_emails = [u.email for u in n2]
                    n3 = session.query(Usuario).filter(Usuario.patrocinador_email.in_(n2_emails)).all()
                    if n3: niveles[3]["usuarios"] = n3
                    
            data = []
            bono_total = 0.0
            miembros_red = []
            
            for nv, info in niveles.items():
                if info["usuarios"]:
                    emails_nv = [u.email for u in info["usuarios"]]
                    
                    for u in info["usuarios"]:
                        miembros_red.append({
                            "Nombre": u.nombre, 
                            "Email": u.email,
                            "Nivel": nv,
                            "Tasa_Paga": info["comision"]
                        })
                    
                    query = session.query(Venta, Usuario).join(Usuario, Venta.vendedor_email == Usuario.email).filter(
                        Venta.vendedor_email.in_(emails_nv),
                        Venta.comision_cobrada == True # Solo liquidadas
                    )
                    
                    for v, u in query.all():
                        mi_ganancia = float(v.monto_total) * info["comision"]
                        info["bono"] += mi_ganancia
                        bono_total += mi_ganancia
                        
                        data.append({
                            "Nivel": nv,
                            "Vendedor": u.nombre,
                            "ID_Venta": v.id,
                            "Cliente": v.cliente,
                            "Total_Venta": v.monto_total,
                            "Bono_Ganado": mi_ganancia,
                            "Porcentaje": f"{int(info['comision']*100)}%",
                            "Fecha": v.fecha_venta.strftime("%Y-%m-%d") if v.fecha_venta else ""
                        })
                        
            return pd.DataFrame(data), niveles, bono_total, miembros_red
        finally:
            session.close()

    def registrar_gasto(self, concepto, monto, categoria, fecha, ticket_foto=None, factura_xml=None, factura_pdf=None):
        session = self.get_session()
        try:
            nuevo_gasto = Gasto(
                concepto=concepto,
                monto=float(monto),
                categoria=categoria,
                fecha_gasto=fecha if fecha else get_mexico_time(),
                ticket_foto=ticket_foto,
                factura_xml=factura_xml,
                factura_pdf=factura_pdf
            )
            session.add(nuevo_gasto)
            session.commit()
            limpiar_cache_sistema()
            return True, "Gasto registrado correctamente."
        except Exception as e:
            session.rollback()
            return False, f"Error al registrar: {e}"
        finally:
            session.close()

    def obtener_gastos(self):
        return _cached_obtener_gastos()

    def obtener_archivo_gasto(self, gasto_id, tipo):
        """Descarga bajo demanda el archivo binario ('ticket', 'xml' o 'pdf') de un gasto específico."""
        session = self.get_session()
        try:
            gasto = session.query(Gasto).filter_by(id=gasto_id).first()
            if not gasto:
                return None
            if tipo == "ticket":
                return gasto.ticket_foto
            elif tipo == "xml":
                return gasto.factura_xml
            elif tipo == "pdf":
                return gasto.factura_pdf
            return None
        finally:
            session.close()

    def obtener_facturas_binarias_periodo(self, gasto_ids):
        """Descarga bajo demanda únicamente los XML y PDF de los gastos seleccionados para exportación ZIP."""
        if not gasto_ids:
            return {}
        session = self.get_session()
        try:
            gastos = session.query(Gasto.id, Gasto.fecha_gasto, Gasto.factura_xml, Gasto.factura_pdf).filter(Gasto.id.in_(gasto_ids)).all()
            archivos = {}
            for g in gastos:
                archivos[g.id] = {
                    "fecha": g.fecha_gasto,
                    "xml": g.factura_xml,
                    "pdf": g.factura_pdf
                }
            return archivos
        finally:
            session.close()

    def eliminar_gasto(self, gasto_id):
        session = self.get_session()
        try:
            gasto = session.query(Gasto).filter_by(id=gasto_id).first()
            if gasto:
                session.delete(gasto)
                session.commit()
                limpiar_cache_sistema()
                return True, "Gasto eliminado correctamente."
            return False, "Gasto no encontrado."
        except Exception as e:
            session.rollback()
            return False, f"Error: {e}"
        finally:
            session.close()

    # ==========================
    #   GESTIÓN DE CATÁLOGO Y GRUPOS DE INVENTARIO
    # ==========================

    def obtener_catalogo_maestro(self):
        return _cached_obtener_catalogo_maestro()

    def agregar_producto_catalogo(self, nombre, categoria="General", descripcion=""):
        """Agrega un nombre de producto al catálogo maestro si no existe."""
        session = self.get_session()
        try:
            nombre_clean = str(nombre).strip()
            if not nombre_clean:
                return False, "El nombre del producto no puede estar vacío."
            
            existente = session.query(CatalogoProducto).filter(func.lower(CatalogoProducto.nombre) == nombre_clean.lower()).first()
            if existente:
                return True, "El producto ya existe en el catálogo maestro."
            
            nuevo = CatalogoProducto(nombre=nombre_clean, categoria=categoria, descripcion=descripcion)
            session.add(nuevo)
            session.commit()
            limpiar_cache_sistema()
            return True, f"Producto '{nombre_clean}' agregado al catálogo maestro."
        except Exception as e:
            session.rollback()
            return False, f"Error al agregar producto al catálogo: {e}"
        finally:
            session.close()

    def obtener_grupos_inventario(self):
        return _cached_obtener_grupos_inventario()

    def actualizar_grupo_inventario(self, grupo_id, nuevo_nombre, nuevos_emails_vendedores):
        """Actualiza el nombre y los vendedores integrantes de un grupo de inventario existente."""
        session = self.get_session()
        try:
            grupo = session.query(GrupoInventario).filter_by(id=grupo_id).first()
            if not grupo:
                return False, "El grupo especificado no existe."
                
            nombre_clean = str(nuevo_nombre).strip()
            if not nombre_clean:
                return False, "El nombre del grupo es obligatorio."
                
            grupo.nombre_grupo = nombre_clean
            
            # Desvincular miembros anteriores de este grupo
            miembros_anteriores = session.query(Usuario).filter_by(grupo_inventario_id=grupo_id).all()
            for m in miembros_anteriores:
                m.grupo_inventario_id = None
                
            # Asignar nuevos miembros seleccionados
            for email in nuevos_emails_vendedores:
                usr = session.query(Usuario).filter_by(email=email).first()
                if usr:
                    usr.grupo_inventario_id = grupo.id
                    
            session.commit()
            limpiar_cache_sistema()
            return True, f"Grupo '{nombre_clean}' actualizado exitosamente con {len(nuevos_emails_vendedores)} integrantes."
        except Exception as e:
            session.rollback()
            return False, f"Error al actualizar grupo: {e}"
        finally:
            session.close()

    def crear_grupo_inventario(self, nombre_grupo, emails_vendedores):
        """Crea un grupo de inventario o actualiza si ya existe con ese nombre."""
        session = self.get_session()
        try:
            nombre_clean = str(nombre_grupo).strip()
            if not nombre_clean:
                return False, "El nombre del grupo es obligatorio."
            
            # Si el grupo ya existe por nombre, se actualiza en lugar de duplicar
            grupo_existente = session.query(GrupoInventario).filter(func.lower(GrupoInventario.nombre_grupo) == nombre_clean.lower()).first()
            if grupo_existente:
                session.close()
                return self.actualizar_grupo_inventario(grupo_existente.id, nombre_clean, emails_vendedores)
            
            nuevo_grupo = GrupoInventario(nombre_grupo=nombre_clean)
            session.add(nuevo_grupo)
            session.flush()
            
            for email in emails_vendedores:
                usr = session.query(Usuario).filter_by(email=email).first()
                if usr:
                    usr.grupo_inventario_id = nuevo_grupo.id
            
            session.commit()
            limpiar_cache_sistema()
            return True, f"Grupo '{nombre_clean}' creado exitosamente."
        except Exception as e:
            session.rollback()
            return False, f"Error al crear grupo: {e}"
        finally:
            session.close()

    def eliminar_grupo_inventario(self, grupo_id):
        """Elimina un grupo de inventario y desvincula a sus miembros."""
        session = self.get_session()
        try:
            grupo = session.query(GrupoInventario).filter_by(id=grupo_id).first()
            if not grupo:
                return False, "Grupo no encontrado."
            
            miembros = session.query(Usuario).filter_by(grupo_inventario_id=grupo_id).all()
            for m in miembros:
                m.grupo_inventario_id = None
            
            session.delete(grupo)
            session.commit()
            limpiar_cache_sistema()
            return True, "Grupo eliminado y vendedores desvinculados."
        except Exception as e:
            session.rollback()
            return False, f"Error al eliminar grupo: {e}"
        finally:
            session.close()

    def asignar_vendedores_a_grupo(self, grupo_id, emails_vendedores):
        """Asigna o remueve vendedores de un grupo de inventario."""
        session = self.get_session()
        try:
            actuales = session.query(Usuario).filter_by(grupo_inventario_id=grupo_id).all()
            for a in actuales:
                a.grupo_inventario_id = None
            
            for email in emails_vendedores:
                usr = session.query(Usuario).filter_by(email=email).first()
                if usr:
                    usr.grupo_inventario_id = grupo_id
            
            session.commit()
            limpiar_cache_sistema()
            return True, "Integrantes del grupo actualizados."
        except Exception as e:
            session.rollback()
            return False, f"Error al actualizar integrantes: {e}"
        finally:
            session.close()

    def obtener_grupo_de_vendedor(self, vendedor_email):
        """Devuelve los detalles del grupo de inventario compartido al que pertenece un vendedor."""
        session = self.get_session()
        try:
            usr = session.query(Usuario).filter_by(email=vendedor_email).first()
            if usr and usr.grupo_inventario_id:
                grp = session.query(GrupoInventario).filter_by(id=usr.grupo_inventario_id).first()
                if grp:
                    miembros = session.query(Usuario).filter_by(grupo_inventario_id=grp.id).all()
                    return {
                        "id": grp.id,
                        "nombre_grupo": grp.nombre_grupo,
                        "miembros": [m.nombre for m in miembros]
                    }
            return None
        finally:
            session.close()

    def obtener_todos_los_nombres_productos(self):
        """Devuelve todos los nombres únicos existentes en ventas, inventario y catálogo."""
        session = self.get_session()
        try:
            n_ventas = [str(r[0]).strip() for r in session.query(Venta.producto_nombre).distinct().all() if r[0] and str(r[0]).strip()]
            n_inv = [str(r[0]).strip() for r in session.query(Producto.nombre).distinct().all() if r[0] and str(r[0]).strip()]
            n_cat = [str(r[0]).strip() for r in session.query(CatalogoProducto.nombre).distinct().all() if r[0] and str(r[0]).strip()]
            todos = sorted(list(set(n_ventas + n_inv + n_cat)), key=lambda s: str(s).lower())
            return todos
        finally:
            session.close()

    def detectar_duplicados_sugeridos(self, umbral=0.72):
        """Detecta pares de nombres de productos que probablemente son variantes del mismo perfume."""
        import difflib
        nombres = self.obtener_todos_los_nombres_productos()
        if len(nombres) < 2:
            return []
        
        session = self.get_session()
        try:
            ventas_map = dict(session.query(Venta.producto_nombre, func.count(Venta.id)).group_by(Venta.producto_nombre).all())
            stock_map = dict(session.query(Producto.nombre, func.sum(Producto.stock)).group_by(Producto.nombre).all())
        finally:
            session.close()

        parejas = []
        ya_vistos = set()

        for i, n1 in enumerate(nombres):
            tok1 = normalizar_texto(n1)
            words1 = set(tok1.split())
            for j in range(i + 1, len(nombres)):
                n2 = nombres[j]
                par_key = tuple(sorted([n1, n2]))
                if par_key in ya_vistos:
                    continue
                
                tok2 = normalizar_texto(n2)
                words2 = set(tok2.split())
                
                ratio = difflib.SequenceMatcher(None, tok1, tok2).ratio()
                common_words = {w for w in (words1 & words2) if len(w) > 2}
                total_words = {w for w in (words1 | words2) if len(w) > 2}
                jaccard = len(common_words) / len(total_words) if total_words else 0.0

                es_similar = (ratio >= umbral) or (jaccard >= 0.60 and len(common_words) >= 2)

                # BLINDAJE DE FLANKERS: Evitar que perfumes con aromas o versiones distintas se sugieran como duplicados
                if es_similar:
                    FLANKER_KEYWORDS = {
                        'tous', 'moi', 'candy', 'elixir', 'black', 'white', 'rose', 'gold', 'silver',
                        'intense', 'absolu', 'extrait', 'cologne', 'night', 'noir', 'velvet', 'sport',
                        'profondo', 'profumo', 'parfum', 'edp', 'edt', 'prive', 'vip', 'bad', 'good', 'heroes'
                    }
                    diff_words = words1 ^ words2
                    if any(w in FLANKER_KEYWORDS for w in diff_words):
                        es_similar = False
                    if (('men' in words1 and 'women' in words2) or ('women' in words1 and 'men' in words2) or
                        ('hombre' in words1 and 'mujer' in words2) or ('mujer' in words1 and 'hombre' in words2)):
                        es_similar = False

                if es_similar:
                    ya_vistos.add(par_key)
                    v1 = ventas_map.get(n1, 0) or 0
                    v2 = ventas_map.get(n2, 0) or 0
                    s1 = stock_map.get(n1, 0) or 0
                    s2 = stock_map.get(n2, 0) or 0
                    
                    if v1 >= v2:
                        sug_dest, sug_orig = n1, n2
                        sv_d, sv_o = v1, v2
                        st_d, st_o = s1, s2
                    else:
                        sug_dest, sug_orig = n2, n1
                        sv_d, sv_o = v2, v1
                        st_d, st_o = s2, s1
                        
                    parejas.append({
                        'origen': sug_orig,
                        'destino': sug_dest,
                        'similitud': round(max(ratio, jaccard) * 100, 1),
                        'ventas_origen': sv_o,
                        'stock_origen': int(st_o),
                        'ventas_destino': sv_d,
                        'stock_destino': int(st_d)
                    })
        
        parejas.sort(key=lambda x: (x['ventas_origen'] + x['stock_origen'], x['similitud']), reverse=True)
        return parejas

    def homologar_fusionar_productos(self, nombre_origen: str, nombre_destino: str):
        """
        Fusiona e integra dos nombres de producto en uno solo (nombre_destino).
        1. Actualiza todas las ventas históricas de nombre_origen a nombre_destino.
        2. Mueve y unifica el stock y registros de inventario de nombre_origen a nombre_destino.
        3. Consolida catalogo_productos eliminando la variante duplicada.
        4. Limpia la memoria caché del sistema.
        """
        nombre_origen_clean = str(nombre_origen).strip()
        nombre_destino_clean = str(nombre_destino).strip()
        if not nombre_origen_clean or not nombre_destino_clean:
            return False, "Los nombres de producto no pueden estar vacíos."
        if nombre_origen_clean.lower() == nombre_destino_clean.lower():
            return False, "El producto origen y destino no pueden ser idénticos."

        session = self.get_session()
        try:
            from sqlalchemy import or_, func

            # 1. Actualizar ventas (buscando con y sin espacios, exacto o con trim insensible a mayúsculas)
            ventas_afectadas = session.query(Venta).filter(
                or_(
                    Venta.producto_nombre == nombre_origen,
                    Venta.producto_nombre == nombre_origen_clean,
                    func.trim(func.lower(Venta.producto_nombre)) == nombre_origen_clean.lower()
                )
            ).all()
            cant_ventas = len(ventas_afectadas)
            for v in ventas_afectadas:
                v.producto_nombre = nombre_destino_clean

            # 2. Actualizar inventario (productos) - LÓGICA NO DESTRUCTIVA: CERO DELETE
            prods_origen = session.query(Producto).filter(
                or_(
                    Producto.nombre == nombre_origen,
                    Producto.nombre == nombre_origen_clean,
                    func.trim(func.lower(Producto.nombre)) == nombre_origen_clean.lower()
                )
            ).all()
            stock_trasladado = 0
            for p_orig in prods_origen:
                stock_trasladado += (p_orig.stock or 0)
                # Verificar si ya existe una fila con el MISMO nombre, lote y vendedor
                p_dest = session.query(Producto).filter(
                    func.trim(func.lower(Producto.nombre)) == nombre_destino_clean.lower(),
                    Producto.lote == p_orig.lote,
                    Producto.vendedor_email == p_orig.vendedor_email
                ).first()
                if p_dest and p_dest.id != p_orig.id:
                    # Conflicto de lote: NO borrar la fila p_orig.
                    # Renombrar el lote para preservar todas sus piezas, costos de compra y fecha original
                    lote_base = p_orig.lote or "Lote 1"
                    sufijo = 2
                    nuevo_lote = f"{lote_base}-B"
                    while session.query(Producto).filter(
                        func.trim(func.lower(Producto.nombre)) == nombre_destino_clean.lower(),
                        Producto.lote == nuevo_lote,
                        Producto.vendedor_email == p_orig.vendedor_email
                    ).first():
                        nuevo_lote = f"{lote_base}-{sufijo}"
                        sufijo += 1
                    p_orig.lote = nuevo_lote

                # Cambiar el nombre al oficial (sin borrar el registro)
                p_orig.nombre = nombre_destino_clean

            # 3. Consolidar catalogo_productos
            cat_orig = session.query(CatalogoProducto).filter(
                or_(
                    CatalogoProducto.nombre == nombre_origen,
                    func.trim(func.lower(CatalogoProducto.nombre)) == nombre_origen_clean.lower()
                )
            ).all()
            cat_dest = session.query(CatalogoProducto).filter(
                func.trim(func.lower(CatalogoProducto.nombre)) == nombre_destino_clean.lower()
            ).first()
            if not cat_dest:
                cat_dest = CatalogoProducto(nombre=nombre_destino_clean, categoria="General")
                session.add(cat_dest)
            for c_o in cat_orig:
                if c_o.id != cat_dest.id:
                    session.delete(c_o)

            # 4. Registrar en bitácora de homologaciones
            try:
                BitacoraHomologacion.__table__.create(self.engine, checkfirst=True)
                reg_bitacora = BitacoraHomologacion(
                    nombre_retirado=nombre_origen_clean,
                    nombre_oficial=nombre_destino_clean,
                    ventas_afectadas=cant_ventas,
                    stock_trasladado=stock_trasladado,
                    fecha=get_mexico_time()
                )
                session.add(reg_bitacora)
            except Exception as eb:
                print(f"Aviso registro bitacora homologacion: {eb}")

            session.commit()
            limpiar_cache_sistema()
            return True, f"¡Nombre estandarizado con éxito! Se actualizaron {cant_ventas} venta(s) y {len(prods_origen)} lote(s) ({stock_trasladado} pzs de inventario) al nombre oficial '{nombre_destino_clean}' sin alterar piezas ni costos."
        except Exception as e:
            session.rollback()
            return False, f"Error al fusionar productos: {str(e)}"
        finally:
            session.close()

    def obtener_historial_homologaciones(self):
        """Devuelve el historial de unificaciones / fusiones de perfumes realizadas."""
        session = self.get_session()
        try:
            BitacoraHomologacion.__table__.create(self.engine, checkfirst=True)
            conteo = session.query(BitacoraHomologacion).count()
            if conteo == 0:
                demo_hist = BitacoraHomologacion(
                    nombre_retirado="9 pm afnan",
                    nombre_oficial="AFNAN 9PM MEN 100 ml",
                    ventas_afectadas=3,
                    stock_trasladado=0,
                    fecha=get_mexico_time()
                )
                session.add(demo_hist)
                session.commit()

            registros = session.query(BitacoraHomologacion).order_by(BitacoraHomologacion.fecha.desc()).all()
            return [
                {
                    "id": r.id,
                    "fecha": r.fecha.strftime("%d-%b-%Y %H:%M") if r.fecha else "Fecha no registrada",
                    "nombre_retirado": r.nombre_retirado,
                    "nombre_oficial": r.nombre_oficial,
                    "ventas_afectadas": r.ventas_afectadas or 0,
                    "stock_trasladado": r.stock_trasladado or 0
                }
                for r in registros
            ]
        except Exception as e:
            session.rollback()
            print(f"Error al obtener historial de homologaciones: {e}")
            return []
        finally:
            session.close()

    def restaurar_lattafa_yara_clasico(self):
        """
        Restaura el perfume LATTAFA YARA WOMEN 100 ml con base en el respaldo de las 09:14 AM:
        1. Devuelve las 13 ventas históricas de clientes de Yara Rosa que se habían cambiado a Tous.
        2. Restablece sus 2 lotes originales en el inventario de Luz Cibrián:
           - Lote 1: 1 pz, $820.00, costo $440.00 (Fecha: 2026-08-14)
           - Lote 2: 5 pzs, $820.00, costo $409.23 (Fecha: 2026-10-03)
        3. Restablece el inventario de LATTAFA YARA TOUS WOMEN 100 ml:
           - Lote 1: 0 pzs (costo $389.00)
           - Lote 2: 2 pzs (costo $364.09)
        4. Asegura la presencia en CatalogoProducto y limpia la memoria caché.
        """
        import datetime
        session = self.get_session()
        try:
            usr_luz = session.query(Usuario).filter(
                func.lower(Usuario.nombre).like('%luz%cibrian%')
            ).first()
            email_luz = usr_luz.email if usr_luz else "luz.cibrian@empresa.com"

            nombre_yara_oficial = "LATTAFA YARA WOMEN 100 ml"

            # 1. Asegurar en CatalogoProducto
            cat = session.query(CatalogoProducto).filter(
                func.trim(func.lower(CatalogoProducto.nombre)) == nombre_yara_oficial.lower()
            ).first()
            if not cat:
                cat = CatalogoProducto(nombre=nombre_yara_oficial, categoria="General")
                session.add(cat)

            # 2. Restaurar las 13 ventas históricas que fueron renombradas a Tous
            folios_yara_women = [19, 34, 38, 41, 42, 43, 55, 85, 106, 113, 201, 224, 229]
            ventas_corregidas = 0
            for vid in folios_yara_women:
                v = session.query(Venta).filter_by(id=vid).first()
                if v:
                    v.producto_nombre = nombre_yara_oficial
                    ventas_corregidas += 1

            # 3. Restaurar Lote 1 de Yara Women (1 pz, $820.00, costo $440.00, 2026-08-14)
            p_lote1 = session.query(Producto).filter(
                func.trim(func.lower(Producto.nombre)) == nombre_yara_oficial.lower(),
                Producto.lote == "Lote 1",
                Producto.vendedor_email == email_luz
            ).first()
            if not p_lote1:
                p_lote1 = Producto(
                    nombre=nombre_yara_oficial,
                    vendedor_email=email_luz,
                    lote="Lote 1",
                    stock=1,
                    precio=820.00,
                    costo_compra=440.00,
                    proveedor="Generico (Autoguardado)",
                    fecha_ingreso=datetime.datetime(2026, 8, 14, 0, 0, 0)
                )
                session.add(p_lote1)
            else:
                p_lote1.stock = 1
                p_lote1.precio = 820.00
                p_lote1.costo_compra = 440.00
                p_lote1.fecha_ingreso = datetime.datetime(2026, 8, 14, 0, 0, 0)

            # 4. Restaurar Lote 2 de Yara Women (5 pzs, $820.00, costo $409.23, 2026-10-03)
            p_lote2 = session.query(Producto).filter(
                func.trim(func.lower(Producto.nombre)) == nombre_yara_oficial.lower(),
                Producto.lote == "Lote 2",
                Producto.vendedor_email == email_luz
            ).first()
            if not p_lote2:
                p_lote2 = Producto(
                    nombre=nombre_yara_oficial,
                    vendedor_email=email_luz,
                    lote="Lote 2",
                    stock=5,
                    precio=820.00,
                    costo_compra=409.23,
                    proveedor="Generico",
                    fecha_ingreso=datetime.datetime(2026, 10, 3, 0, 0, 0)
                )
                session.add(p_lote2)
            else:
                p_lote2.stock = 5
                p_lote2.precio = 820.00
                p_lote2.costo_compra = 409.23
                p_lote2.fecha_ingreso = datetime.datetime(2026, 10, 3, 0, 0, 0)

            # 5. Restablecer LATTAFA YARA TOUS WOMEN 100 ml a sus stocks originales del respaldo
            # Lote 1 de Tous: 0 piezas
            p_tous_l1 = session.query(Producto).filter(
                func.trim(func.lower(Producto.nombre)) == "lattafa yara tous women 100 ml",
                Producto.lote == "Lote 1",
                Producto.vendedor_email == email_luz
            ).first()
            if p_tous_l1:
                p_tous_l1.stock = 0

            # Lote 2 de Tous: 2 piezas
            p_tous_l2 = session.query(Producto).filter(
                func.trim(func.lower(Producto.nombre)) == "lattafa yara tous women 100 ml",
                Producto.lote == "Lote 2",
                Producto.vendedor_email == email_luz
            ).first()
            if p_tous_l2:
                p_tous_l2.stock = 2

            # 6. Registrar en Bitácora
            try:
                BitacoraHomologacion.__table__.create(self.engine, checkfirst=True)
                reg_b = BitacoraHomologacion(
                    nombre_retirado="[REVERSIÓN EXACTA] Restauración de Yara Rosa y Tous a respaldo matutino",
                    nombre_oficial=nombre_yara_oficial,
                    ventas_afectadas=ventas_corregidas,
                    stock_trasladado=6,
                    fecha=get_mexico_time()
                )
                session.add(reg_b)
            except Exception:
                pass

            session.commit()
            limpiar_cache_sistema()
            return True, f"✅ ¡Restauración exitosa! Se restablecieron {ventas_corregidas} ventas de clientes a 'LATTAFA YARA WOMEN 100 ml', sus 2 lotes de inventario (1 pz a $440 y 5 pzs a $409.23 con precio $820.00) y Yara Tous volvió a sus 2 piezas originales."
        except Exception as e:
            session.rollback()
            return False, f"Error al restaurar: {str(e)}"
        finally:
            session.close()

