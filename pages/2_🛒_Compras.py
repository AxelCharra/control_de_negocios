import streamlit as st
import datetime
import time
from utils.auth import requerir_login
import utils.db_queries as db

st.set_page_config(page_title="Compras", page_icon="🛒", layout="wide")

# Protejo la página
requerir_login()
usuario_actual = st.session_state['usuario_logueado']

st.title("🛒 Registro de Compras")

tab1, tab2, tab3 = st.tabs(["➕ Ingresar Mercadería", "📋 Historial de Compras", "✏️ Editar Compra"])

# --- Pestaña 1: Ingreso de nueva mercadería ---
with tab1:
    st.subheader("Ingresar mercadería y actualizar costos")
    
    df_productos = db.obtener_inventario(usuario_actual)
    
    if df_productos.empty:
        st.warning("⚠️ Primero tenés que crear productos en el Inventario.")
    else:
        opciones_prod = dict(zip(df_productos['nombre'], df_productos['id']))
        producto_seleccionado = st.selectbox("Seleccionar Producto", options=list(opciones_prod.keys()))
        
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.date_input("Fecha de compra", datetime.date.today())
            # A la cantidad le pongo value=None para que arranque limpia
            cantidad = st.number_input("Cantidad de unidades", min_value=1, value=None, placeholder="0", step=1)
            proveedor = st.text_input("Proveedor (Opcional)")
            
        with col2:
            # Aplicamos el truco de value=None y placeholder para UX fluida
            costo_unitario = st.number_input("Costo Unitario de Compra ($)", min_value=0.0, value=None, placeholder="0.0", step=100.0)
            margen = st.number_input("Ganancia esperada (%)", min_value=0.0, value=None, placeholder="0", step=5.0)
            
            # Parche matemático: Si el campo está vacío (None), lo trato como 0 para que no se rompa el cálculo
            val_costo = costo_unitario if costo_unitario is not None else 0.0
            val_margen = margen if margen is not None else 0.0
            
            # Calculo el precio sugerido en vivo con los valores seguros
            precio_calculado = val_costo * (1 + (val_margen / 100))
            st.info(f"💡 Nuevo precio de venta sugerido: **${precio_calculado:,.2f}**")
            
        if st.button("Registrar Ingreso y Actualizar Precios"):
            # Valido que los campos no estén vacíos (None)
            if cantidad is None or cantidad < 1:
                st.warning("Por favor ingresá una cantidad válida.")
            elif costo_unitario is None or costo_unitario <= 0:
                st.warning("El costo unitario debe ser mayor a 0.")
            elif margen is None:
                st.warning("Por favor ingresá un porcentaje de ganancia (puede ser 0).")
            else:
                prod_id = opciones_prod[producto_seleccionado]
                
                # Desempaquetamos el éxito y el mensaje matemático (PPP) de la base de datos
                exito, msj = db.registrar_compra(usuario_actual, prod_id, fecha, int(cantidad), float(costo_unitario), proveedor, float(margen), precio_calculado)
                
                if exito:
                    st.success(msj)
                    # Freno 3.5 segundos para que llegues a leer la nueva matemática antes de que se limpie
                    time.sleep(3.5)
                    st.rerun()
                else:
                    st.error(msj)

# --- Pestaña 2: Historial ---
with tab2:
    st.subheader("Historial de Compras")
    
    query_historial = """
    SELECT c.fecha, p.nombre as producto, c.cantidad, c.costo_unitario, c.costo_total, c.proveedor
    FROM compras c
    JOIN productos p ON c.producto_id = p.id
    WHERE c.usuario = %s
    ORDER BY c.fecha DESC;
    """
    df_compras = db.ejecutar_consulta_lectura(query_historial, (usuario_actual,))
    
    if df_compras.empty:
        st.info("Todavía no registraste ninguna compra.")
    else:
        st.dataframe(df_compras, use_container_width=True, hide_index=True)

# --- Pestaña 3: Edición y Anulación ---
with tab3:
    st.subheader("Modificar o Anular una compra")
    
    query_historial_completo = """
    SELECT c.id as compra_id, p.id as producto_id, c.fecha, p.nombre as producto, 
           c.cantidad, c.costo_unitario, c.costo_total, c.proveedor
    FROM compras c
    JOIN productos p ON c.producto_id = p.id
    WHERE c.usuario = %s
    ORDER BY c.fecha DESC;
    """
    df_historial_edicion = db.ejecutar_consulta_lectura(query_historial_completo, (usuario_actual,))
    
    if df_historial_edicion.empty:
        st.info("No hay compras registradas para editar.")
    else:
        opciones_edicion = {}
        for _, row in df_historial_edicion.iterrows():
            texto_opcion = f"ID: {row['compra_id']} | {row['fecha']} - {row['producto']} (Cant: {row['cantidad']})"
            opciones_edicion[texto_opcion] = row
            
        compra_seleccionada = st.selectbox("Seleccioná el registro exacto:", options=["-- Elegir una compra --"] + list(opciones_edicion.keys()))
        
        if compra_seleccionada != "-- Elegir una compra --":
            datos_compra = opciones_edicion[compra_seleccionada]
            
            # --- 1. TICKET VIRTUAL ---
            with st.container(border=True):
                st.markdown(f"### 🧾 Ticket de Compra #{datos_compra['compra_id']}")
                col_t1, col_t2, col_t3 = st.columns(3)
                col_t1.metric("Producto", datos_compra['producto'])
                col_t1.metric("Fecha", str(datos_compra['fecha']))
                col_t2.metric("Cantidad Ingresada", f"{datos_compra['cantidad']} u.")
                col_t2.metric("Proveedor", datos_compra['proveedor'] if datos_compra['proveedor'] else "No registrado")
                col_t3.metric("Costo Unitario", f"${float(datos_compra['costo_unitario']):,.2f}")
                col_t3.metric("Total Pagado", f"${float(datos_compra['costo_total']):,.2f}")
            
            st.markdown("---")
            
            # --- 2. SEPARACIÓN DE FLUJOS (RADIO BUTTON) ---
            accion = st.radio("¿Qué acción querés realizar con este registro?", ["✏️ Editar valores", "🚨 Anular definitivamente"], horizontal=True)
            
            if accion == "✏️ Editar valores":
                st.info("Vas a modificar las cantidades o costos. El stock y tu contabilidad se ajustarán automáticamente.")
                with st.form("form_editar_compra"):
                    col1, col2 = st.columns(2)
                    with col1:
                        nueva_fecha = st.date_input("Fecha", datos_compra['fecha'])
                        nueva_cantidad = st.number_input("Cantidad", min_value=1, value=int(datos_compra['cantidad']), step=1)
                    with col2:
                        nuevo_costo = st.number_input("Costo Unitario ($)", min_value=0.0, value=float(datos_compra['costo_unitario']), step=10.0)
                        prov_actual = datos_compra['proveedor'] if datos_compra['proveedor'] else ""
                        nuevo_proveedor = st.text_input("Proveedor", value=prov_actual)
                        
                    if st.form_submit_button("💾 Guardar Cambios"):
                        exito, msj = db.editar_compra(
                            usuario_actual, datos_compra['compra_id'], datos_compra['producto_id'], 
                            nueva_fecha, nueva_cantidad, nuevo_costo, nuevo_proveedor
                        )
                        if exito:
                            st.success(f"{msj} Podés verificarlo en el Historial.")
                            time.sleep(2.5)
                            st.rerun()
                        else:
                            st.error(msj)
                            
            elif accion == "🚨 Anular definitivamente":
                st.error("⚠️ Atención: Esta acción borrará la compra del historial y **restará la mercadería de tu stock actual**. No se puede deshacer.")
                if st.button("Anular Compra", type="primary"):
                    exito, msj = db.anular_compra(usuario_actual, datos_compra['compra_id'], datos_compra['producto_id'])
                    if exito:
                        st.success(f"{msj} Revisá el Historial.")
                        time.sleep(2.5)
                        st.rerun()
                    else:
                        st.error(msj)