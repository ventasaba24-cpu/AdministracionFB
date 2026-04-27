import os
import pandas as pd
import datetime
import streamlit as st
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, ForeignKey, text, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func

Base = declarative_base()

# --- MODELOS DE DATOS ---

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

class IntentoSeguridad(Base):
    __tablename__ = 'intentos_seguridad'
    id = Column(Integer, primary_key=True, autoincrement=True)
    identificador = Column(String(100), nullable=False, unique=True) # IP o Email atacado
    fallos = Column(Integer, default=0)
    bloqueado_hasta = Column(DateTime, nullable=True)
    ultimo_intento = Column(DateTime, default=datetime.datetime.utcnow)

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
    
    __table_args__ = (UniqueConstraint('nombre', 'lote', 'vendedor_email', name='_nombre_lote_vendedor_uc'),)

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
    fecha_abono = Column(DateTime, default=datetime.datetime.utcnow)
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
    fecha_gasto = Column(DateTime, default=datetime.datetime.utcnow)
    ticket_foto = Column(LargeBinary, nullable=True)

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
    
    # Migración silenciosa de SQLite para no molestar al usuario con comandos manuales
    if "sqlite" in db_path:
        engine = create_engine(db_path, connect_args={"check_same_thread": False})
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE ventas ADD COLUMN fecha_cobro_comision DATETIME"))
                 conn.execute(text("UPDATE ventas SET fecha_cobro_comision = fecha_venta WHERE comision_cobrada = 1 AND fecha_cobro_comision IS NULL"))
                 conn.commit()
        except:
             pass # Ya existe
             
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE usuarios ADD COLUMN patrocinador_email VARCHAR(100)"))
                 conn.commit()
        except:
             pass
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE usuarios ADD COLUMN tipo_vendedor VARCHAR(50) DEFAULT 'Crédito'"))
                 conn.commit()
        except:
             pass
             
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE usuarios ADD COLUMN session_token VARCHAR(100)"))
                 conn.commit()
        except:
             pass
             
        try:
             with engine.connect() as conn:
                 conn.execute(text("UPDATE usuarios SET patrocinador_email = (SELECT email FROM usuarios WHERE rol = 'Admin' ORDER BY id ASC LIMIT 1) WHERE patrocinador_email IS NULL AND rol != 'Admin'"))
                 conn.commit()
        except:
             pass
    else:
        # Entorno PostgreSQL (Nube Supabase)
        engine = create_engine(db_path, pool_pre_ping=True, pool_size=5, max_overflow=10)
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE ventas ADD COLUMN fecha_cobro_comision TIMESTAMP"))
                 conn.execute(text("UPDATE ventas SET fecha_cobro_comision = fecha_venta WHERE comision_cobrada = true AND fecha_cobro_comision IS NULL"))
                 conn.commit()
        except:
             pass # Ya existe la columna
             
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE usuarios ADD COLUMN patrocinador_email VARCHAR(100)"))
                 conn.commit()
        except:
             pass
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE usuarios ADD COLUMN tipo_vendedor VARCHAR(50) DEFAULT 'Crédito'"))
                 conn.commit()
        except:
             pass
             
        try:
             with engine.connect() as conn:
                 conn.execute(text("ALTER TABLE usuarios ADD COLUMN session_token VARCHAR(100)"))
                 conn.commit()
        except:
             pass
             
        try:
             with engine.connect() as conn:
                 conn.execute(text("UPDATE usuarios SET patrocinador_email = (SELECT email FROM usuarios WHERE rol = 'Admin' ORDER BY id ASC LIMIT 1) WHERE patrocinador_email IS NULL AND rol != 'Admin'"))
                 conn.commit()
        except:
             pass
        
    Base.metadata.create_all(engine)
    SessionMaker = sessionmaker(bind=engine, expire_on_commit=False)
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
                    password=generate_password_hash("admin"),
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
                    password=generate_password_hash("123"),
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
            # Respaldar los costos de compra y proveedores actuales (para no sobreescribirlos si es un vendedor quien guarda)
            old_products = session.query(Producto).filter_by(vendedor_email=vendedor_email).all()
            costos_map = {f"{p.nombre}-{p.lote}": p.costo_compra for p in old_products}
            provs_map = {f"{p.nombre}-{p.lote}": p.proveedor for p in old_products}
            
            # Borramos el previo stock de este vendedor
            session.query(Producto).filter_by(vendedor_email=vendedor_email).delete(synchronize_session=False)
            
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
                    
                nuevo_prod = Producto(
                    nombre=nombre,
                    vendedor_email=vendedor_email,
                    stock=int(row.get('stock', 0)),
                    precio=float(row.get('precio', 0.0)),
                    costo_compra=float(costo_nuevo),
                    proveedor=str(prov_nuevo),
                    lote=lote
                )
                session.add(nuevo_prod)
            session.commit()
            return True, "Inventario sincronizado."
        except Exception as e:
            session.rollback()
            return False, str(e)
        finally:
            session.close()

    def upsert_producto(self, vendedor_email, datos, producto_id=None):
        session = self.get_session()
        try:
            if producto_id:
                prod = session.query(Producto).filter_by(id=producto_id, vendedor_email=vendedor_email).first()
                if not prod:
                    return False, "Producto no encontrado."
                prod.nombre = str(datos["nombre"]).strip()
                prod.lote = str(datos.get("lote", "Lote 1")).strip()
                prod.precio = float(datos.get("precio", 0.0))
                prod.costo_compra = float(datos.get("costo_compra", 0.0))
                prod.proveedor = str(datos.get("proveedor", "Generico")).strip()
                prod.stock = int(datos.get("stock", 0))
            else:
                prod = Producto(
                    nombre=str(datos["nombre"]).strip(),
                    vendedor_email=vendedor_email,
                    lote=str(datos.get("lote", "Lote 1")).strip(),
                    precio=float(datos.get("precio", 0.0)),
                    costo_compra=float(datos.get("costo_compra", 0.0)),
                    proveedor=str(datos.get("proveedor", "Generico")).strip(),
                    stock=int(datos.get("stock", 0))
                )
                session.add(prod)
            session.commit()
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
            productos_lotes = session.query(Producto).filter_by(nombre=producto_nombre, vendedor_email=vendedor_email).filter(Producto.stock > 0).order_by(Producto.id.asc()).all()
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
            
            # FIFO Logic (First In, First Out) by Lote
            productos_lotes = session.query(Producto).filter_by(nombre=producto, vendedor_email=vendedor_email).order_by(Producto.id.asc()).all()
            
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
                fecha_venta=datetime.datetime.now()
            )
            session.add(nueva_venta)
                
            session.commit()
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
            return True, "Costo y Nombre corregidos satisfactoriamente."
        except Exception as e:
            session.rollback()
            return False, f"Error: {str(e)}"
        finally:
            session.close()

    def registrar_abono(self, venta_id, monto, metodo="Efectivo", fecha_abono=None):
        session = self.get_session()
        if fecha_abono is None:
            fecha_abono = datetime.datetime.now()
        
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
                 venta.fecha_cobro_comision = datetime.datetime.utcnow()
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
        Calcula dinámicamente el DataFrame enlazando Ventas + Abonos y generando Estados.
        (Optimizado para evitar el problema de N+1 queries en la Nube)
        """
        session = self.get_session()
        try:
             from sqlalchemy.orm import joinedload
             # Traemos ventas con sus abonos en UNA sola ida (eager loading)
             ventas = session.query(Venta).options(joinedload(Venta.abonos)).all()
             # Traemos todos los usuarios en UNA sola ida para el diccionario
             usuarios = session.query(Usuario).all()
             user_dict = {u.email: u for u in usuarios}
             
             # Diccionario rápido de productos para sacar su proveedor
             productos = session.query(Producto).all()
             prod_dict = {(p.nombre, p.vendedor_email): p for p in productos}
             
             datos_procesados = []
             
             for v in ventas:
                 # Ya no hay query aquí, usamos la data ya en memoria
                 abonos_query = v.abonos
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
                 
                 # Busqueda súper rápida en memoria
                 vendedor = user_dict.get(v.vendedor_email)
                 tasa = vendedor.tasa_comision if vendedor else 0.10
                 nombre_vendedor = vendedor.nombre if vendedor else "Desconocido"
                 
                 prod = prod_dict.get((v.producto_nombre, v.vendedor_email))
                 nombre_proveedor = prod.proveedor if prod and prod.proveedor else "Desconocido"
                 
                 # Si está pagado
                 comision_ganada = v.monto_total * tasa
                 comision_pagada = "SI" if estado == "Pagado" else "NO"
                 
                 # RASTREADOR MLM O(1) (Penalización oculta de 5%, 3%, 2%)
                 comision_red = 0.0
                 comision_red_l1 = 0.0
                 comision_red_l2 = 0.0
                 comision_red_l3 = 0.0
                 niveles_red_activos = 0
                 
                 if vendedor:
                     p1 = vendedor.patrocinador_email
                     if p1 and p1 != "Admin" and p1 != v.vendedor_email:
                         comision_red_l1 = v.monto_total * 0.05
                         comision_red += comision_red_l1
                         niveles_red_activos += 1
                         user_p1 = user_dict.get(p1)
                         
                         if user_p1:
                             p2 = user_p1.patrocinador_email
                             if p2 and p2 != "Admin" and p2 != p1:
                                 comision_red_l2 = v.monto_total * 0.03
                                 comision_red += comision_red_l2
                                 niveles_red_activos += 1
                                 user_p2 = user_dict.get(p2)
                                 
                                 if user_p2:
                                     p3 = user_p2.patrocinador_email
                                     if p3 and p3 != "Admin" and p3 != p2:
                                         comision_red_l3 = v.monto_total * 0.02
                                         comision_red += comision_red_l3
                                         niveles_red_activos += 1
                 
                 # === METRICAS FINANCIERAS NETAS ===
                 iva_generado = v.monto_total * 0.16
                 costo_bases = getattr(v, "costo_historico", 0.0) # Asegurando compatibilidad con DBs previas
                 utilidad_neta = v.monto_total - iva_generado - costo_bases - comision_ganada - comision_red
                 
                 fila = {
                     "ID_Venta": v.id,
                     "Fecha_Venta": v.fecha_venta.strftime("%d-%b-%Y") if v.fecha_venta else "",
                     "Dias_Ultimo_Abono": dias_ultimo,
                     "Nombre_Vendedor": nombre_vendedor,
                     "Vendedor_Email": v.vendedor_email,
                     "Cliente": v.cliente,
                     "Producto": v.producto_nombre,
                     "Cantidad": getattr(v, "cantidad", 1),
                     "Proveedor": nombre_proveedor,
                     "Total_Venta": v.monto_total,
                     "IVA_(16%)": iva_generado,
                     "Costo_Producto": costo_bases,
                     "Total_Abono": total_abonos,
                     "Saldo_Pendiente": saldo,
                     "Estado_Venta": estado,
                     "Comision_Generada": comision_ganada,
                     "Comision_Red": comision_red,
                     "Comision_Red_L1": comision_red_l1,
                     "Comision_Red_L2": comision_red_l2,
                     "Comision_Red_L3": comision_red_l3,
                     "Niveles_Red": niveles_red_activos,
                     "Utilidad_Neta": utilidad_neta,
                     "Comision_Pagada": comision_pagada, # Concepto teórico de si ya superó el Adeudo
                     "Comision_Fisicamente_Cobrada": v.comision_cobrada,
                     "Fecha_Cobro_Comision": v.fecha_cobro_comision.strftime("%d-%b-%Y") if hasattr(v, "fecha_cobro_comision") and v.fecha_cobro_comision else ""
                 }
                 datos_procesados.append(fila)
                 
             return pd.DataFrame(datos_procesados)

        finally:
            session.close()

    def eliminar_venta(self, venta_id):
        session = self.get_session()
        try:
            venta = session.query(Venta).filter_by(id=venta_id).first()
            if not venta:
                return False, "Venta no encontrada."
            
            # Devolver stock
            mi_producto = session.query(Producto).filter_by(nombre=venta.producto_nombre, vendedor_email=venta.vendedor_email).first()
            if mi_producto:
                mi_producto.stock += venta.cantidad
                
            session.delete(venta) # Cascada eliminará Abonos adjuntos
            session.commit()
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
            
            # Si el producto o la cantidad cambió, ajustamos el stock matemáticamente
            if venta.producto_nombre != nuevo_producto or venta.cantidad != cantidad_int:
                # 1. Devolver el producto viejo al inventario
                prod_viejo = session.query(Producto).filter_by(nombre=venta.producto_nombre, vendedor_email=venta.vendedor_email).first()
                if prod_viejo:
                    prod_viejo.stock += venta.cantidad
                
                # 2. Descontar el producto nuevo del inventario
                prod_nuevo = session.query(Producto).filter_by(nombre=nuevo_producto, vendedor_email=venta.vendedor_email).first()
                if prod_nuevo:
                    prod_nuevo.stock = max(0, prod_nuevo.stock - cantidad_int)
                    
            venta.cliente = nuevo_cliente
            venta.producto_nombre = nuevo_producto
            venta.cantidad = cantidad_int
            venta.monto_total = monto_float
            venta.costo_historico = costo_float
            
            session.commit()
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
            return True, "Recibo actualizado correctamente."
        except Exception as e:
            session.rollback()
            return False, f"Error al actualizar abono: {e}"
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
    #   USUARIOS Y AUTENTICACIÓN LOGIC PÚBLICA
    # ==========================
    
    def verificar_y_registrar_intento(self, session, identificador):
        """Verifica si un identificador (IP o Email) está bloqueado por demasiados intentos. Si no, lo deja pasar (True), si sí, devuelve (False)"""
        registro = session.query(IntentoSeguridad).filter_by(identificador=identificador).first()
        if not registro:
            return True, None # No hay registro, puede intentar
            
        if registro.bloqueado_hasta and registro.bloqueado_hasta > datetime.datetime.utcnow():
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
            if registro.bloqueado_hasta and registro.bloqueado_hasta <= datetime.datetime.utcnow():
                 registro.fallos = 1
                 registro.bloqueado_hasta = None
            else:
                 registro.fallos += 1
            
            if registro.fallos >= 3:
                # Bloquear por 15 minutos en UTC
                registro.bloqueado_hasta = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        
        registro.ultimo_intento = datetime.datetime.utcnow()
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
                 resta = tiempo_bloqueo - datetime.datetime.utcnow()
                 minutos_restantes = max(1, int(resta.total_seconds() / 60))
                 return False, None, None, f"Por seguridad tecnológica, este acceso ha sido temporalmente suspendido. Intente de nuevo en {minutos_restantes} minutos."
             
             # Buscar existencial
             usr = session.query(Usuario).filter_by(email=email).first()
             
             # Fallo intencional temprano si no existe el correo
             if not usr:
                 self.registrar_fallo(session, id_seguridad)
                 return False, None, None, "Credenciales inválidas."
                 
             # Validar el hash
             if not check_password_hash(usr.password, password):
                 # Chequeo legacy temporal por si hay contraseñas en texto plano de BD viejas (opcional pero ayuda en transición)
                 if usr.password == password:
                     # Migración silenciosa
                     usr.password = generate_password_hash(password)
                     session.commit()
                 else:
                     self.registrar_fallo(session, id_seguridad)
                     return False, None, None, "Credenciales inválidas."
             
             # Si llegó aquí, todo está bien
             import uuid
             nuevo_token = str(uuid.uuid4())
             usr.session_token = nuevo_token
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
        session = self.get_session()
        try:
            query = session.query(Usuario).filter(Usuario.rol != "Admin")
            df = pd.read_sql(query.statement, session.bind)
            return df
        finally:
            session.close()

    def registrar_vendedor(self, nombre, email, password, comision=0.10, patrocinador_email=None, tipo_vendedor="Crédito"):
        session = self.get_session()
        try:
            nuevo = Usuario(
                nombre=nombre,
                email=email,
                password=generate_password_hash(password),
                rol="Vendedor",
                tasa_comision=comision/100.0, # Guardar directo como tasa decimal (10% -> 0.10)
                patrocinador_email=patrocinador_email,
                tipo_vendedor=tipo_vendedor
            )
            session.add(nuevo)
            session.commit()
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

    def registrar_gasto(self, concepto, monto, categoria, fecha, ticket_foto=None):
        session = self.get_session()
        try:
            nuevo_gasto = Gasto(
                concepto=concepto,
                monto=float(monto),
                categoria=categoria,
                fecha_gasto=fecha if fecha else datetime.datetime.utcnow(),
                ticket_foto=ticket_foto
            )
            session.add(nuevo_gasto)
            session.commit()
            return True, "Gasto registrado correctamente."
        except Exception as e:
            session.rollback()
            return False, f"Error al registrar: {e}"
        finally:
            session.close()

    def obtener_gastos(self):
        session = self.get_session()
        try:
            gastos = session.query(Gasto).order_by(Gasto.fecha_gasto.desc()).all()
            data = []
            for g in gastos:
                data.append({
                    "ID": g.id,
                    "Concepto": g.concepto,
                    "Monto": g.monto,
                    "Categoria": g.categoria,
                    "Fecha": g.fecha_gasto.strftime("%d-%m-%Y %H:%M") if g.fecha_gasto else "",
                    "Tiene_Foto": True if g.ticket_foto else False,
                    "Foto_Bytes": g.ticket_foto
                })
            return pd.DataFrame(data)
        finally:
            session.close()

    def eliminar_gasto(self, gasto_id):
        session = self.get_session()
        try:
            gasto = session.query(Gasto).filter_by(id=gasto_id).first()
            if gasto:
                session.delete(gasto)
                session.commit()
                return True, "Gasto eliminado correctamente."
            return False, "Gasto no encontrado."
        except Exception as e:
            session.rollback()
            return False, f"Error: {e}"
        finally:
            session.close()
