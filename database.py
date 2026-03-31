import os
import pandas as pd
import datetime
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# --- MODELOS DE DATOS ---

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    rol = Column(String(50), default='Vendedor') # 'Admin' o 'Vendedor'
    tasa_comision = Column(Float, default=0.10) # 10% por defecto basado en los datos brindados

from sqlalchemy import UniqueConstraint

class Producto(Base):
    __tablename__ = 'productos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(150), nullable=False)
    vendedor_email = Column(String(100), ForeignKey('usuarios.email', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    stock = Column(Integer, default=0)
    precio = Column(Float, nullable=False)
    
    __table_args__ = (UniqueConstraint('nombre', 'vendedor_email', name='_nombre_vendedor_uc'),)

class Venta(Base):
    __tablename__ = 'ventas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_venta = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Llaves foráneas
    vendedor_email = Column(String(100), ForeignKey('usuarios.email', onupdate='CASCADE', ondelete='CASCADE'))
    cliente = Column(String(150), nullable=False)
    producto_nombre = Column(String(150), nullable=False) # Guardamos el nombre del producto en el momento de la venta
    
    cantidad = Column(Integer, default=1)
    # Total Venta
    monto_total = Column(Float, nullable=False)
    
    comision_cobrada = Column(Boolean, default=False) # Bandera que indica si el vendedor ya cobro los billetes físicos
    
    # Relaciones
    abonos = relationship("Abono", back_populates="venta", cascade="all, delete-orphan")

class Abono(Base):
    __tablename__ = 'abonos'
    id_abono = Column(Integer, primary_key=True, autoincrement=True)
    venta_id = Column(Integer, ForeignKey('ventas.id'), nullable=False)
    fecha_abono = Column(DateTime, default=datetime.datetime.utcnow)
    monto_abono = Column(Float, nullable=False)
    metodo_pago = Column(String(50), default="Tranferencia")
    
    # Campo opcional guardando texto o ubicación
    comprobante_foto = Column(String(255), nullable=True)
    
    venta = relationship("Venta", back_populates="abonos")

# --- CONTROLADOR CENTRAL DE BASE DE DATOS ---

@st.cache_resource(show_spinner="Conectando base de datos...")
def init_db_connection(default_path='sqlite:///erp_database.db'):
    db_path = default_path
    try:
        if "SUPABASE_URL" in st.secrets:
            db_url = st.secrets["SUPABASE_URL"]
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            db_path = db_url
    except Exception:
        pass
        
    print(f"🔌 Inicializando pool de conexiones: {'[NUBE PostgreSQL]' if 'postgresql' in db_path else '[LOCAL SQLite]'}")
    
    if "sqlite" in db_path:
        engine = create_engine(db_path, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(db_path, pool_pre_ping=True, pool_size=5, max_overflow=10)
        
    Base.metadata.create_all(engine)
    SessionMaker = sessionmaker(bind=engine)
    return engine, SessionMaker

class DatabaseHandler:
    def __init__(self):
        # Reutiliza el Pool de Conexión global guardado en RAM por Streamlit
        self.engine, self.Session = init_db_connection()
        self.inicializar_datos_demo()

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
                    password="admin",
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
                    password="123",
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
        """Devuelve el inventario en formato DataFrame de Pandas. Si no se provee email, devuelve todos."""
        session = self.get_session()
        try:
            query = session.query(Producto)
            if vendedor_email:
                query = query.filter_by(vendedor_email=vendedor_email)
            df = pd.read_sql(query.statement, session.bind)
            return df
        finally:
            session.close()
            
    def guardar_inventario(self, df_inventario, vendedor_email):
        """Sobreescribe el inventario de un vendedor específico basado en el DataFrame del UI."""
        session = self.get_session()
        try:
            # Borramos el previo stock de este vendedor
            session.query(Producto).filter_by(vendedor_email=vendedor_email).delete(synchronize_session=False)
            
            for index, row in df_inventario.iterrows():
                # Ignorar filas vacías
                nombre = str(row.get('nombre', '')).strip()
                if not nombre or pd.isna(row.get('nombre')):
                    continue
                nuevo_prod = Producto(
                    nombre=nombre,
                    vendedor_email=vendedor_email,
                    stock=int(row.get('stock', 0)),
                    precio=float(row.get('precio', 0.0))
                )
                session.add(nuevo_prod)
            session.commit()
            return True, "Inventario sincronizado."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def actualizar_stock(self, producto_nombre, cantidad_vendida, vendedor_email):
        session = self.get_session()
        try:
            producto = session.query(Producto).filter_by(nombre=producto_nombre, vendedor_email=vendedor_email).first()
            if producto:
                producto.stock = max(0, producto.stock - cantidad_vendida)
                session.commit()
                return True
            return False
        finally:
            session.close()

    # ==========================
    #   OPERACIONES VENTAS Y ABONOS (CON LÓGICA DE NEGOCIO PANDAS)
    # ==========================
    
    def registrar_venta(self, vendedor_email, cliente, producto, cantidad, precio_unitario):
        session = self.get_session()
        try:
            monto_total = float(cantidad) * float(precio_unitario)
            nueva_venta = Venta(
                vendedor_email=vendedor_email,
                cliente=cliente,
                producto_nombre=producto,
                cantidad=cantidad,
                monto_total=monto_total,
                fecha_venta=datetime.datetime.now()
            )
            session.add(nueva_venta)
            
            # Auto - Actualizar Stock
            mi_producto = session.query(Producto).filter_by(nombre=producto, vendedor_email=vendedor_email).first()
            if mi_producto:
                mi_producto.stock = max(0, mi_producto.stock - cantidad)
                
            session.commit()
            return True, nueva_venta.id, monto_total
        except Exception as e:
            session.rollback()
            print(f"Error al registrar venta: {e}")
            return False, None, 0.0
        finally:
            session.close()

    def registrar_abono(self, venta_id, monto, metodo="Efectivo"):
        session = self.get_session()
        try:
            venta_existe = session.query(Venta).filter_by(id=venta_id).first()
            if not venta_existe:
                return False, "Esa ID de Venta no existe."
                
            nuevo_abono = Abono(
                venta_id=venta_id,
                monto_abono=monto,
                fecha_abono=datetime.datetime.now(),
                metodo_pago=metodo
            )
            session.add(nuevo_abono)
            session.commit()
            return True, "Abono registrado con éxito."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def marcar_comision_cobrada(self, venta_id):
        session = self.get_session()
        try:
             venta = session.query(Venta).filter_by(id=venta_id).first()
             if venta:
                 venta.comision_cobrada = True
                 session.commit()
                 return True, "Se ha registrado el cobro de esta comisión."
             return False, "Venta no encontrada."
        except Exception as e:
             session.rollback()
             return False, str(e)
        finally:
             session.close()

    def obtener_tabla_ventas_completa(self):
        """
        Calcula dinámicamente el DataFrame idéntico al que compartiste
        enlazando Ventas + Abonos y generando Estados.
        """
        session = self.get_session()
        try:
             ventas = session.query(Venta).all()
             datos_procesados = []
             
             for v in ventas:
                 # Ventas sumatorias nativas
                 abonos_query = session.query(Abono).filter_by(venta_id=v.id).all()
                 total_abonos = sum([a.monto_abono for a in abonos_query])
                 
                 # Dias ultimo abono
                 dias_ultimo = None
                 if abonos_query:
                     # Sacar el mas reciente
                     fechas_abono = [a.fecha_abono for a in abonos_query if a.fecha_abono]
                     if fechas_abono:
                         ultimo = max(fechas_abono)
                         diferencia = datetime.datetime.now() - ultimo
                         dias_ultimo = diferencia.days
                 
                 # Si no tiene abono, usar fecha de inicio de venta
                 if dias_ultimo is None:
                     if v.fecha_venta:
                         dias_ultimo = (datetime.datetime.now() - v.fecha_venta).days
                     else:
                         dias_ultimo = 0
                 
                 saldo = v.monto_total - total_abonos
                 estado = "Pagado" if saldo <= 0 else "Adeudo"
                 
                 # Quien lo vendio y su comision teórica
                 vendedor = session.query(Usuario).filter_by(email=v.vendedor_email).first()
                 tasa = vendedor.tasa_comision if vendedor else 0.10
                 nombre_vendedor = vendedor.nombre if vendedor else "Desconocido"
                 
                 # Si está pagado
                 comision_ganada = v.monto_total * tasa
                 comision_pagada = "SI" if estado == "Pagado" else "NO"
                 
                 fila = {
                     "ID_Venta": v.id,
                     "Fecha_Venta": v.fecha_venta.strftime("%d-%b-%Y") if v.fecha_venta else "",
                     "Dias_Ultimo_Abono": dias_ultimo,
                     "Nombre_Vendedor": nombre_vendedor,
                     "Cliente": v.cliente,
                     "Producto": v.producto_nombre,
                     "Total_Venta": v.monto_total,
                     "Total_Abono": total_abonos,
                     "Saldo_Pendiente": saldo,
                     "Estado_Venta": estado,
                     "Comision_Generada": comision_ganada,
                     "Comision_Pagada": comision_pagada, # Concepto teórico de si ya superó el Adeudo
                     "Comision_Fisicamente_Cobrada": v.comision_cobrada
                 }
                 datos_procesados.append(fila)
                 
             return pd.DataFrame(datos_procesados)

        finally:
            session.close()

    def leer_abonos(self):
        session = self.get_session()
        try:
            query = session.query(Abono)
            df = pd.read_sql(query.statement, session.bind)
            return df
        finally:
            session.close()

    # ==========================
    #   USUARIOS Y AUTENTICACIÓN
    # ==========================
    def login(self, email, password):
        session = self.get_session()
        try:
             usr = session.query(Usuario).filter_by(email=email, password=password).first()
             if usr:
                 return True, usr
             return False, None
        finally:
             session.close()

    def get_user_by_email(self, email):
        session = self.get_session()
        try:
             usr = session.query(Usuario).filter_by(email=email).first()
             return usr
        finally:
             session.close()

    def obtener_vendedores(self):
        session = self.get_session()
        try:
            query = session.query(Usuario).filter(Usuario.rol != "Admin")
            df = pd.read_sql(query.statement, session.bind)
            return df
        finally:
            session.close()

    def registrar_vendedor(self, nombre, email, password, comision=0.10):
        session = self.get_session()
        try:
            nuevo = Usuario(
                nombre=nombre,
                email=email,
                password=password,
                rol="Vendedor",
                tasa_comision=comision/100.0 # Guardar directo como tasa decimal (10% -> 0.10)
            )
            session.add(nuevo)
            session.commit()
            return True, "Registrado en SQLite."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()
