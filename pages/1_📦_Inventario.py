import streamlit as st
from utils.auth import requerir_login
import utils.db_queries as db

st.set_page_config(page_title="Inventario", page_icon="📦", layout="wide")

# Protejo la página
requerir_login()

# Tomo el usuario actual de la sesión
usuario_actual = st.session_state['usuario_logueado']

st.title("📦 Gestión de Inventario")

# Agregamos una tercera pestaña para las eliminaciones
tab1, tab2, tab3 = st.tabs(["📋 Listado de Productos", "➕ Agregar Nuevo", "🗑️ Eliminar"])

with tab1:
    st.subheader("Stock Actual")
    df_inventario = db.obtener_inventario(usuario_actual)
    
    if df_inventario.empty:
        st.info("No tenés productos cargados todavía. Andá a la pestaña 'Agregar Nuevo'.")
    else:
        st.dataframe(df_inventario, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Alta de Productos y Categorías")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**1. Crear Categoría**")
        with st.form("form_categoria", clear_on_submit=True):
            nueva_categoria = st.text_input("Nombre de la categoría")
            submit_cat = st.form_submit_button("Guardar Categoría")
            
            if submit_cat:
                if nueva_categoria.strip():
                    if db.crear_categoria(usuario_actual, nueva_categoria.strip()):
                        st.success(f"Categoría '{nueva_categoria}' creada!")
                        st.rerun() 
                else:
                    st.warning("Ingresá un nombre válido.")
    
    with col2:
        st.markdown("**2. Crear Producto**")
        df_categorias = db.obtener_categorias(usuario_actual)
        
        if df_categorias.empty:
            st.warning("Primero creá una categoría a la izquierda.")
        else:
            opciones_cat = dict(zip(df_categorias['nombre'], df_categorias['id']))
            
            with st.form("form_producto", clear_on_submit=True):
                nombre_prod = st.text_input("Nombre del producto")
                categoria_seleccionada = st.selectbox("Categoría", options=list(opciones_cat.keys()))
                submit_prod = st.form_submit_button("Guardar Producto")
                
                if submit_prod:
                    if not nombre_prod.strip():
                        st.error("El producto necesita un nombre.")
                    else:
                        cat_id = opciones_cat[categoria_seleccionada]
                        if db.crear_producto(usuario_actual, nombre_prod.strip(), cat_id):
                            st.success(f"Producto '{nombre_prod}' creado. (Costos y stock se definen en Compras).")
                            st.rerun()

# --- Nueva pestaña de Eliminación ---
with tab3:
    st.subheader("Eliminar Registros")
    st.markdown("⚠️ **Atención:** Solo podés eliminar categorías vacías y productos sin historial comercial.")
    
    col_del_cat, col_del_prod = st.columns(2)
    
    with col_del_cat:
        st.markdown("**Borrar Categoría**")
        df_categorias = db.obtener_categorias(usuario_actual)
        
        if not df_categorias.empty:
            opciones_cat = dict(zip(df_categorias['nombre'], df_categorias['id']))
            cat_a_borrar = st.selectbox("Seleccionar Categoría", options=list(opciones_cat.keys()), key="del_cat")
            
            if st.button("🗑️ Eliminar Categoría", type="primary"):
                cat_id = opciones_cat[cat_a_borrar]
                exito, mensaje = db.eliminar_categoria(usuario_actual, cat_id)
                if exito:
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error(mensaje)
        else:
            st.info("No hay categorías para eliminar.")
            
    with col_del_prod:
        st.markdown("**Borrar Producto**")
        
        # Uso df_inventario que ya consulté en tab1 (si lo querés siempre fresco, podés volver a consultar)
        df_inv_borrar = db.obtener_inventario(usuario_actual)
        
        if not df_inv_borrar.empty:
            opciones_prod = dict(zip(df_inv_borrar['nombre'], df_inv_borrar['id']))
            prod_a_borrar = st.selectbox("Seleccionar Producto", options=list(opciones_prod.keys()), key="del_prod")
            
            if st.button("🗑️ Eliminar Producto", type="primary"):
                prod_id = opciones_prod[prod_a_borrar]
                exito, mensaje = db.eliminar_producto(usuario_actual, prod_id)
                if exito:
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error(mensaje)
        else:
            st.info("No hay productos para eliminar.")