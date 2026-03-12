import streamlit as st
import datetime
from utils.auth import requerir_login
import utils.db_queries as db

st.set_page_config(page_title="Ventas", page_icon="💵", layout="wide")

requerir_login()
usuario_actual = st.session_state['usuario_logueado']

st.title("💵 Registro de Ventas")

tab1, tab2, tab3 = st.tabs(["➕ Nueva Venta", "📋 Historial de Ventas", "✏️ Editar o Anular"])

with tab1:
    st.subheader("Cargar operación")
    df_inventario = db.obtener_inventario(usuario_actual)
    
    if df_inventario.empty:
        st.warning("⚠️ No tenés productos en el inventario. Agregá productos primero.")
    else:
        with st.form("form_venta", clear_on_submit=True):
            opciones_prod = dict(zip(df_inventario['nombre'], df_inventario['id']))
            stock_prod = dict(zip(df_inventario['nombre'], df_inventario['stock_actual']))
            precio_sugerido = dict(zip(df_inventario['nombre'], df_inventario['precio_venta_sugerido']))
            
            producto_seleccionado = st.selectbox("Seleccionar Producto", options=list(opciones_prod.keys()))
            stock_disponible = stock_prod.get(producto_seleccionado, 0)
            st.caption(f"📦 Stock disponible: **{stock_disponible} unidades**")
            
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha de venta", datetime.date.today())
                # Truco UX: value=None para que arranque vacío y no haya que borrar el 0
                cantidad = st.number_input("Cantidad", min_value=1, value=None, placeholder="0", step=1)
            with col2:
                # Acá NO usamos value=None porque queremos que sugiera el precio automáticamente
                precio_base = float(precio_sugerido.get(producto_seleccionado, 0.0))
                precio_unitario = st.number_input("Precio de venta (Unidad)", min_value=0.0, value=precio_base, step=100.0)
                cliente = st.text_input("Cliente (Opcional)")
                
            submit_venta = st.form_submit_button("Registrar Venta")
            
            if submit_venta:
                # Validamos que la cantidad no esté vacía antes de hacer la matemática
                if cantidad is None or cantidad < 1:
                    st.warning("Por favor ingresá una cantidad válida.")
                elif cantidad > stock_disponible:
                    st.error(f"❌ No podés vender {cantidad} unidades. Solo tenés {stock_disponible} en stock.")
                elif precio_unitario <= 0:
                    st.warning("El precio debe ser mayor a 0.")
                else:
                    prod_id = opciones_prod[producto_seleccionado]
                    # Convertimos cantidad a entero por las dudas al mandarlo a la DB
                    if db.registrar_venta(usuario_actual, prod_id, fecha, int(cantidad), precio_unitario, cliente):
                        st.success(f"¡Venta registrada! Se descontaron {cantidad} unidades.")
                        st.rerun()

with tab2:
    st.subheader("Historial de Operaciones")
    df_ventas = db.obtener_ventas(usuario_actual)
    
    if df_ventas.empty:
        st.info("Todavía no registraste ninguna venta.")
    else:
        st.dataframe(df_ventas, use_container_width=True, hide_index=True)

# --- Pestaña 3: Edición y Anulación ---
with tab3:
    st.subheader("Modificar o Anular una venta")
    
    query_historial_ventas = """
    SELECT v.id as venta_id, p.id as producto_id, v.fecha, p.nombre as producto, 
           v.cantidad, v.precio_unitario, v.total, v.cliente
    FROM ventas v
    JOIN productos p ON v.producto_id = p.id
    WHERE v.usuario = %s
    ORDER BY v.fecha DESC;
    """
    df_historial_ventas = db.ejecutar_consulta_lectura(query_historial_ventas, (usuario_actual,))
    
    if df_historial_ventas.empty:
        st.info("No hay ventas registradas para modificar o anular.")
    else:
        opciones_edicion_ventas = {}
        for _, row in df_historial_ventas.iterrows():
            texto_opcion = f"ID: {row['venta_id']} | {row['fecha']} - {row['producto']} (Vendidas: {row['cantidad']})"
            opciones_edicion_ventas[texto_opcion] = row
            
        venta_seleccionada = st.selectbox("Seleccioná el registro exacto:", options=["-- Elegir una venta --"] + list(opciones_edicion_ventas.keys()))
        
        if venta_seleccionada != "-- Elegir una venta --":
            datos_venta = opciones_edicion_ventas[venta_seleccionada]
            
            # --- 1. TICKET VIRTUAL ---
            with st.container(border=True):
                st.markdown(f"### 🧾 Ticket de Venta #{datos_venta['venta_id']}")
                col_t1, col_t2, col_t3 = st.columns(3)
                col_t1.metric("Producto", datos_venta['producto'])
                col_t1.metric("Fecha", str(datos_venta['fecha']))
                col_t2.metric("Cantidad Vendida", f"{datos_venta['cantidad']} u.")
                col_t2.metric("Cliente", datos_venta['cliente'] if datos_venta['cliente'] else "Consumidor Final")
                col_t3.metric("Precio Unitario", f"${float(datos_venta['precio_unitario']):,.2f}")
                col_t3.metric("Total Cobrado", f"${float(datos_venta['total']):,.2f}")
                
            st.markdown("---")
            
            # --- 2. SEPARACIÓN DE FLUJOS (RADIO BUTTON) ---
            accion_v = st.radio("¿Qué acción querés realizar con este registro?", ["✏️ Editar valores", "🚨 Anular definitivamente"], horizontal=True)
            
            if accion_v == "✏️ Editar valores":
                st.info("Vas a modificar las cantidades o precios. El stock se ajustará automáticamente.")
                with st.form("form_editar_venta"):
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        nueva_fecha = st.date_input("Fecha", datos_venta['fecha'], key="fecha_v")
                        nueva_cantidad = st.number_input("Cantidad", min_value=1, value=int(datos_venta['cantidad']), step=1, key="cant_v")
                    with col_v2:
                        nuevo_precio = st.number_input("Precio de venta ($)", min_value=0.0, value=float(datos_venta['precio_unitario']), step=10.0, key="precio_v")
                        cliente_actual = datos_venta['cliente'] if datos_venta['cliente'] else ""
                        nuevo_cliente = st.text_input("Cliente", value=cliente_actual, key="cliente_v")
                        
                    if st.form_submit_button("💾 Guardar Cambios"):
                        exito, msj = db.editar_venta(
                            usuario_actual, datos_venta['venta_id'], datos_venta['producto_id'], 
                            nueva_fecha, nueva_cantidad, nuevo_precio, nuevo_cliente
                        )
                        if exito:
                            st.success(f"{msj} Podés verificarlo en el Historial.")
                            import time 
                            time.sleep(2.5)
                            st.rerun()
                        else:
                            st.error(msj)
                            
            elif accion_v == "🚨 Anular definitivamente":
                st.error("⚠️ Atención: Esta acción borrará la venta del historial y **devolverá la mercadería a tu stock actual**. No se puede deshacer.")
                if st.button("Anular Venta", type="primary"):
                    exito, msj = db.anular_venta(usuario_actual, datos_venta['venta_id'], datos_venta['producto_id'])
                    if exito:
                        st.success(f"{msj} Revisá el Historial.")
                        import time
                        time.sleep(2.5)
                        st.rerun()
                    else:
                        st.error(msj)