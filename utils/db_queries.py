import pandas as pd
import streamlit as st
from utils.db_connection import init_connection
import hashlib

# --- Función nueva para asegurar que la conexión esté viva ---
def obtener_conexion_activa():
    # Traigo la conexión de la caché de Streamlit
    conn = init_connection()
    
    # Verifico si Neon cerró la conexión (0 = abierta, distinto de 0 = cerrada)
    if conn.closed != 0:
        # Si está cerrada, borro esta función específica de la caché
        init_connection.clear()
        # Vuelvo a conectarme para obtener una conexión fresca
        conn = init_connection()
        
    return conn

# --- Funciones Auxiliares Actualizadas ---
def ejecutar_consulta_lectura(query, params=None):
    # Uso mi nueva función para garantizar que la conexión funcione
    conn = obtener_conexion_activa()
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        st.error(f"Error al leer base de datos: {e}")
        return pd.DataFrame()

def ejecutar_consulta_escritura(query, params=None):
    # Uso mi nueva función para garantizar que la conexión funcione
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            cur.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            st.error(f"Error al guardar datos: {e}")
            return False

# --- Consultas del Inventario ---
def obtener_categorias(usuario):
    query = "SELECT id, nombre FROM categorias WHERE usuario = %s ORDER BY nombre;"
    return ejecutar_consulta_lectura(query, (usuario,))

def crear_categoria(usuario, nombre):
    query = "INSERT INTO categorias (usuario, nombre) VALUES (%s, %s);"
    return ejecutar_consulta_escritura(query, (usuario, nombre))

def obtener_inventario(usuario):
    # Traigo los productos sumando las nuevas columnas de costos y márgenes
    query = """
    SELECT p.id, p.nombre, c.nombre as categoria, p.stock_actual, 
           p.costo_compra, p.porcentaje_ganancia, p.precio_venta_sugerido
    FROM productos p
    LEFT JOIN categorias c ON p.categoria_id = c.id
    WHERE p.usuario = %s
    ORDER BY p.nombre;
    """
    return ejecutar_consulta_lectura(query, (usuario,))

def crear_producto(usuario, nombre, categoria_id):
    # Guardo el producto solo con el nombre y la categoría. Todo empieza en 0.
    query = """
    INSERT INTO productos (usuario, nombre, categoria_id, stock_actual, costo_compra, porcentaje_ganancia, precio_venta_sugerido)
    VALUES (%s, %s, %s, 0, 0, 0, 0);
    """
    return ejecutar_consulta_escritura(query, (usuario, nombre, categoria_id))

def registrar_compra(usuario, producto_id, fecha, cantidad, costo_unitario, proveedor, porcentaje_ganancia, precio_sugerido_ui):
    costo_total_compra = cantidad * costo_unitario
    
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Traigo los datos actuales del producto (Stock y Costo actual)
            cur.execute("SELECT stock_actual, costo_compra FROM productos WHERE id = %s AND usuario = %s;", (producto_id, usuario))
            resultado = cur.fetchone()
            
            stock_previo = resultado[0] if resultado else 0
            costo_previo = float(resultado[1]) if resultado and resultado[1] else 0.0
            
            # 2. LA MAGIA DEL COSTO PROMEDIO PONDERADO
            valor_inventario_previo = stock_previo * costo_previo
            valor_compra_nueva = cantidad * costo_unitario
            nuevo_stock_total = stock_previo + cantidad
            
            # Evito la división por cero por si es el primer producto
            if nuevo_stock_total > 0:
                nuevo_costo_promedio = (valor_inventario_previo + valor_compra_nueva) / nuevo_stock_total
            else:
                nuevo_costo_promedio = costo_unitario
                
            # 3. Recalculo el precio sugerido con el nuevo costo promedio real
            nuevo_precio_sugerido = nuevo_costo_promedio * (1 + (porcentaje_ganancia / 100))
            
            # 4. Guardo el ticket de compra (Acá guardamos el costo REAL de esta transacción histórica)
            query_compra = """
            INSERT INTO compras (usuario, producto_id, fecha, cantidad, costo_unitario, costo_total, proveedor)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            cur.execute(query_compra, (usuario, producto_id, fecha, cantidad, costo_unitario, costo_total_compra, proveedor))
            
            # 5. Actualizo el producto con el stock total y los precios unificados
            query_stock = """
            UPDATE productos 
            SET stock_actual = %s,
                costo_compra = %s,
                porcentaje_ganancia = %s,
                precio_venta_sugerido = %s
            WHERE id = %s AND usuario = %s;
            """
            cur.execute(query_stock, (nuevo_stock_total, nuevo_costo_promedio, porcentaje_ganancia, nuevo_precio_sugerido, producto_id, usuario))
            
            conn.commit()
            
            # Armo un mensaje dinámico para mostrarle al usuario la matemática final
            mensaje_exito = f"¡Compra registrada! El nuevo Costo Promedio unificado es ${nuevo_costo_promedio:,.2f} y tu precio sugerido cambió a ${nuevo_precio_sugerido:,.2f}."
            return True, mensaje_exito
            
        except Exception as e:
            conn.rollback()
            return False, f"Error al registrar compra: {e}"

def obtener_compras(usuario):
    # Traigo el historial uniendo la tabla compras con productos para ver el nombre
    query = """
    SELECT c.fecha, p.nombre as producto, c.cantidad, c.costo_unitario, c.costo_total, c.proveedor
    FROM compras c
    JOIN productos p ON c.producto_id = p.id
    WHERE c.usuario = %s
    ORDER BY c.fecha DESC;
    """
    return ejecutar_consulta_lectura(query, (usuario,))

    # --- Consultas de Usuarios (SaaS) ---
def obtener_usuarios():
    # Traigo todos los usuarios para que el sistema valide el login
    query = "SELECT username, email, nombre, password_hash FROM usuarios;"
    return ejecutar_consulta_lectura(query)

def registrar_usuario(username, email, nombre, password_hash):
    # Guardo un nuevo cliente en la base de datos de Neon
    query = """
    INSERT INTO usuarios (username, email, nombre, password_hash)
    VALUES (%s, %s, %s, %s);
    """
    return ejecutar_consulta_escritura(query, (username, email, nombre, password_hash))

# --- Consultas de Ventas ---
def registrar_venta(usuario, producto_id, fecha, cantidad, precio_unitario, cliente):
    # Calculo el ingreso total de esta operación
    total = cantidad * precio_unitario
    
    # Preparo las dos consultas: guardar la venta y restar el inventario
    query_venta = """
    INSERT INTO ventas (usuario, producto_id, fecha, cantidad, precio_unitario, total, cliente)
    VALUES (%s, %s, %s, %s, %s, %s, %s);
    """
    query_stock = """
    UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s AND usuario = %s;
    """
    
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # Ejecuto ambas acciones en bloque
            cur.execute(query_venta, (usuario, producto_id, fecha, cantidad, precio_unitario, total, cliente))
            cur.execute(query_stock, (cantidad, producto_id, usuario))
            conn.commit()
            return True
        except Exception as e:
            # Si algo sale mal, cancelo la transacción
            conn.rollback()
            st.error(f"Error al registrar la venta: {e}")
            return False

def obtener_ventas(usuario):
    # Traigo el historial cruzando datos con la tabla de productos
    query = """
    SELECT v.fecha, p.nombre as producto, v.cantidad, v.precio_unitario, v.total, v.cliente
    FROM ventas v
    JOIN productos p ON v.producto_id = p.id
    WHERE v.usuario = %s
    ORDER BY v.fecha DESC;
    """
    return ejecutar_consulta_lectura(query, (usuario,))

# --- Consultas de Eliminación ---
def eliminar_categoria(usuario, categoria_id):
    # Intento borrar la categoría. Si tiene productos adentro, Postgres frenará la acción.
    query = "DELETE FROM categorias WHERE id = %s AND usuario = %s;"
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            cur.execute(query, (categoria_id, usuario))
            conn.commit()
            return True, "Categoría eliminada con éxito."
        except Exception as e:
            conn.rollback()
            return False, "No se puede eliminar: primero debés borrar o cambiar los productos que usan esta categoría."

def eliminar_producto(usuario, producto_id):
    # Intento borrar el producto. Si tiene compras o ventas, Postgres frenará la acción.
    query = "DELETE FROM productos WHERE id = %s AND usuario = %s;"
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            cur.execute(query, (producto_id, usuario))
            conn.commit()
            return True, "Producto eliminado con éxito."
        except Exception as e:
            conn.rollback()
            return False, "No se puede eliminar: este producto ya tiene un historial de compras o ventas asociado."
        
# --- Edición de Transacciones ---
def editar_compra(usuario, compra_id, producto_id, nueva_fecha, nueva_cantidad, nuevo_costo, nuevo_proveedor):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Busco cuántas unidades tenía la compra original
            cur.execute("SELECT cantidad FROM compras WHERE id = %s AND usuario = %s;", (compra_id, usuario))
            resultado = cur.fetchone()
            if not resultado:
                return False, "No se encontró la compra."
            
            cantidad_original = resultado[0]
            
            # 2. Calculo el ajuste (Si antes compré 10 y ahora 15, la diferencia es +5 al stock)
            diferencia_stock = nueva_cantidad - cantidad_original
            nuevo_total = nueva_cantidad * nuevo_costo
            
            # 3. Actualizo el registro de la compra
            query_compra = """
            UPDATE compras 
            SET fecha = %s, cantidad = %s, costo_unitario = %s, costo_total = %s, proveedor = %s
            WHERE id = %s AND usuario = %s;
            """
            cur.execute(query_compra, (nueva_fecha, nueva_cantidad, nuevo_costo, nuevo_total, nuevo_proveedor, compra_id, usuario))
            
            # 4. Impacto la diferencia en el inventario
            query_stock = """
            UPDATE productos 
            SET stock_actual = stock_actual + %s 
            WHERE id = %s AND usuario = %s;
            """
            cur.execute(query_stock, (diferencia_stock, producto_id, usuario))
            
            # Guardo los cambios
            conn.commit()
            return True, "Compra actualizada y stock ajustado correctamente."
            
        except Exception as e:
            conn.rollback()
            return False, f"Error al editar la compra: {e}"
        
# --- Edición de Ventas ---
def editar_venta(usuario, venta_id, producto_id, nueva_fecha, nueva_cantidad, nuevo_precio, nuevo_cliente):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Busco la cantidad original de la venta y el stock actual del producto
            cur.execute("SELECT cantidad FROM ventas WHERE id = %s AND usuario = %s;", (venta_id, usuario))
            res_venta = cur.fetchone()
            if not res_venta:
                return False, "No se encontró la venta."
            cantidad_original = res_venta[0]
            
            cur.execute("SELECT stock_actual FROM productos WHERE id = %s AND usuario = %s;", (producto_id, usuario))
            res_stock = cur.fetchone()
            stock_actual = res_stock[0]
            
            # 2. Calculo la diferencia (Si antes vendí 10 y ahora 15, diferencia = 5)
            diferencia_ventas = nueva_cantidad - cantidad_original
            
            # 3. Validación clave: ¿Tengo stock para cubrir ese aumento?
            if diferencia_ventas > stock_actual:
                return False, f"Stock insuficiente. Querés sumar {diferencia_ventas} unidades a la venta, pero solo tenés {stock_actual} en stock."
            
            nuevo_total = nueva_cantidad * nuevo_precio
            
            # 4. Actualizo el registro de la venta
            query_venta = """
            UPDATE ventas 
            SET fecha = %s, cantidad = %s, precio_unitario = %s, total = %s, cliente = %s
            WHERE id = %s AND usuario = %s;
            """
            cur.execute(query_venta, (nueva_fecha, nueva_cantidad, nuevo_precio, nuevo_total, nuevo_cliente, venta_id, usuario))
            
            # 5. Impacto la diferencia en el inventario (RESTO la diferencia)
            query_stock = """
            UPDATE productos 
            SET stock_actual = stock_actual - %s 
            WHERE id = %s AND usuario = %s;
            """
            cur.execute(query_stock, (diferencia_ventas, producto_id, usuario))
            
            # Guardo los cambios
            conn.commit()
            return True, "Venta actualizada y stock ajustado correctamente."
            
        except Exception as e:
            conn.rollback()
            return False, f"Error al editar la venta: {e}"
        
# --- Anulación de Transacciones ---
def anular_venta(usuario, venta_id, producto_id):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Busco cuántas unidades se habían vendido en esa operación
            cur.execute("SELECT cantidad FROM ventas WHERE id = %s AND usuario = %s;", (venta_id, usuario))
            resultado = cur.fetchone()
            if not resultado:
                return False, "No se encontró la venta."
            
            cantidad_vendida = resultado[0]
            
            # 2. Le devuelvo ese stock al producto en el inventario
            query_stock = """
            UPDATE productos 
            SET stock_actual = stock_actual + %s 
            WHERE id = %s AND usuario = %s;
            """
            cur.execute(query_stock, (cantidad_vendida, producto_id, usuario))
            
            # 3. Borro definitivamente el ticket de venta
            query_delete = "DELETE FROM ventas WHERE id = %s AND usuario = %s;"
            cur.execute(query_delete, (venta_id, usuario))
            
            conn.commit()
            return True, "Venta anulada con éxito. El stock fue devuelto al inventario."
            
        except Exception as e:
            conn.rollback()
            return False, f"Error al anular la venta: {e}"

# --- Anulación de Compras ---
def anular_compra(usuario, compra_id, producto_id):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Traigo la cantidad que se había comprado
            cur.execute("SELECT cantidad FROM compras WHERE id = %s AND usuario = %s;", (compra_id, usuario))
            res_compra = cur.fetchone()
            if not res_compra:
                return False, "No se encontró la compra."
            cantidad_comprada = res_compra[0]
            
            # 2. Reviso el stock actual. ¡No puedo anular si ya vendí esa mercadería!
            cur.execute("SELECT stock_actual FROM productos WHERE id = %s AND usuario = %s;", (producto_id, usuario))
            stock_actual = cur.fetchone()[0]
            
            if stock_actual < cantidad_comprada:
                return False, f"⚠️ No podés anular esta compra. Ya vendiste parte de esta mercadería y tu stock quedaría en negativo (Stock actual: {stock_actual})."
            
            # 3. Le resto ese stock al producto en el inventario
            query_stock = "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s AND usuario = %s;"
            cur.execute(query_stock, (cantidad_comprada, producto_id, usuario))
            
            # 4. Borro definitivamente el ticket de compra
            query_delete = "DELETE FROM compras WHERE id = %s AND usuario = %s;"
            cur.execute(query_delete, (compra_id, usuario))
            
            conn.commit()
            return True, "Compra anulada con éxito. El stock fue descontado."
            
        except Exception as e:
            conn.rollback()
            return False, f"Error al anular la compra: {e}"

# --- Anulación de Compras ---
def anular_compra(usuario, compra_id, producto_id):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Traigo la cantidad que se había comprado
            cur.execute("SELECT cantidad FROM compras WHERE id = %s AND usuario = %s;", (compra_id, usuario))
            res_compra = cur.fetchone()
            if not res_compra:
                return False, "No se encontró la compra."
            cantidad_comprada = res_compra[0]
            
            # 2. Reviso el stock actual. ¡No puedo anular si ya vendí esa mercadería!
            cur.execute("SELECT stock_actual FROM productos WHERE id = %s AND usuario = %s;", (producto_id, usuario))
            stock_actual = cur.fetchone()[0]
            
            if stock_actual < cantidad_comprada:
                return False, f"⚠️ No podés anular esta compra. Ya vendiste parte de esta mercadería y tu stock quedaría en negativo (Stock actual: {stock_actual})."
            
            # 3. Le resto ese stock al producto en el inventario
            query_stock = "UPDATE productos SET stock_actual = stock_actual - %s WHERE id = %s AND usuario = %s;"
            cur.execute(query_stock, (cantidad_comprada, producto_id, usuario))
            
            # 4. Borro definitivamente el ticket de compra
            query_delete = "DELETE FROM compras WHERE id = %s AND usuario = %s;"
            cur.execute(query_delete, (compra_id, usuario))
            
            conn.commit()
            return True, "Compra anulada con éxito. El stock fue descontado."
            
        except Exception as e:
            conn.rollback()
            return False, f"Error al anular la compra: {e}"
        
# --- Consultas para el Dashboard ---

def obtener_kpis(usuario):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # 1. Total de ingresos por ventas
            cur.execute("SELECT COALESCE(SUM(total), 0) FROM ventas WHERE usuario = %s;", (usuario,))
            total_ventas = cur.fetchone()[0]
            
            # 2. Total de plata invertida en compras
            cur.execute("SELECT COALESCE(SUM(costo_total), 0) FROM compras WHERE usuario = %s;", (usuario,))
            total_compras = cur.fetchone()[0]
            
            # 3. Capital inmovilizado (El valor de tu mercadería actual usando tu Costo Promedio)
            cur.execute("SELECT COALESCE(SUM(stock_actual * costo_compra), 0) FROM productos WHERE usuario = %s;", (usuario,))
            valor_inventario = cur.fetchone()[0]
            
            return float(total_ventas), float(total_compras), float(valor_inventario)
        except Exception as e:
            return 0.0, 0.0, 0.0

def obtener_ventas_por_dia(usuario):
    query = """
    SELECT fecha, SUM(total) as ingresos, SUM(cantidad) as unidades
    FROM ventas
    WHERE usuario = %s
    GROUP BY fecha
    ORDER BY fecha ASC;
    """
    return ejecutar_consulta_lectura(query, (usuario,))
    
def obtener_top_productos(usuario):
    query = """
    SELECT p.nombre as "Producto", SUM(v.cantidad) as "Unidades Vendidas", SUM(v.total) as "Ingresos Generados"
    FROM ventas v
    JOIN productos p ON v.producto_id = p.id
    WHERE v.usuario = %s
    GROUP BY p.nombre
    ORDER BY "Unidades Vendidas" DESC
    LIMIT 5;
    """
    return ejecutar_consulta_lectura(query, (usuario,))

# --- SISTEMA DE AUTENTICACIÓN ---

def hashear_password(password):
    import hashlib # Por si no lo pusiste arriba de todo
    return hashlib.sha256(password.encode()).hexdigest()

def registrar_usuario(usuario, email, nombre, negocio, password):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # Verificamos si el usuario o el email ya existen
            cur.execute("SELECT id FROM usuarios WHERE usuario = %s OR email = %s;", (usuario, email))
            if cur.fetchone():
                return False, "El usuario o correo ya están registrados."
            
            pw_hash = hashear_password(password)
            
            # Ahora insertamos los 4 campos: usuario, email, nombre y negocio
            cur.execute(
                "INSERT INTO usuarios (usuario, email, nombre, negocio, password_hash) VALUES (%s, %s, %s, %s, %s);",
                (usuario, email, nombre, negocio, pw_hash)
            )
            conn.commit()
            return True, "¡Cuenta creada con éxito! Ya podés ingresar."
        except Exception as e:
            conn.rollback()
            return False, f"Error al registrar: {e}"

def verificar_credenciales(identificador, password):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # Busco tanto por usuario como por email
            cur.execute("SELECT password_hash, username FROM usuarios WHERE username = %s OR email = %s;", (identificador, identificador))
            resultado = cur.fetchone()
            
            if resultado:
                db_hash, db_username = resultado
                if db_hash == hashear_password(password):
                    # Si coincide, devuelvo True y el nombre de usuario real para la sesión
                    return True, db_username 
            return False, None
        except Exception as e:
            return False, None

def recuperar_password(email, nueva_password):
    conn = obtener_conexion_activa()
    with conn.cursor() as cur:
        try:
            # Verifico que el email exista en la base de datos
            cur.execute("SELECT id FROM usuarios WHERE email = %s;", (email,))
            if not cur.fetchone():
                return False, "El correo no coincide con nuestros registros."
            
            # Si existe, actualizo la contraseña de ese correo
            pw_hash = hashear_password(nueva_password)
            cur.execute("UPDATE usuarios SET password_hash = %s WHERE email = %s;", (pw_hash, email))
            conn.commit()
            return True, "¡Contraseña actualizada con éxito! Ya podés ingresar."
        except Exception as e:
            conn.rollback()
            return False, f"Error al recuperar contraseña: {e}"