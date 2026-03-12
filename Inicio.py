import streamlit as st
import pandas as pd
import utils.db_queries as db

st.set_page_config(page_title="Inicio - Dashboard", page_icon="📊", layout="wide")

# --- 1. SISTEMA DE LOGIN, REGISTRO Y RECUPERACIÓN ---
if 'usuario_logueado' not in st.session_state:
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.title("🔐 Acceso al Sistema")
            
            # Agregamos la tercera pestaña
            tab_login, tab_registro, tab_recuperar = st.tabs(["Ingresar", "Crear Cuenta", "Olvidé mi contraseña"])
            
            # --- PESTAÑA INGRESAR ---
            with tab_login:
                with st.form("login_form"):
                    identificador_input = st.text_input("Usuario o Correo Electrónico").lower().strip()
                    password_input = st.text_input("Contraseña", type="password")
                    submit_login = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)
                    
                    if submit_login:
                        if not identificador_input or not password_input:
                            st.warning("Completá ambos campos.")
                        else:
                            exito, nombre_usuario_real = db.verificar_credenciales(identificador_input, password_input)
                            if exito:
                                st.session_state['usuario_logueado'] = nombre_usuario_real
                                st.rerun()
                            else:
                                st.error("❌ Credenciales incorrectas.")
            
            # --- PESTAÑA REGISTRO ---
            with tab_registro:
                with st.form("registro_form"):
                    st.markdown("Completá los datos para registrar tu cuenta.")
                    
                    # Pedimos los datos personales y comerciales
                    reg_nombre = st.text_input("Tu nombre personal (Ej: Juan)").strip()
                    reg_negocio = st.text_input("Nombre de tu negocio (Ej: Moda Showroom)").strip()
                    
                    # Datos de acceso
                    st.markdown("---")
                    reg_usuario = st.text_input("Elige un nombre de usuario (sin espacios)").lower().strip()
                    reg_email = st.text_input("Correo electrónico").lower().strip()
                    reg_nueva_pass = st.text_input("Crea una contraseña", type="password")
                    reg_confirma_pass = st.text_input("Repite la contraseña", type="password")
                    
                    submit_registro = st.form_submit_button("Registrarse", use_container_width=True)
                    
                    if submit_registro:
                        if not reg_usuario or not reg_email or not reg_nueva_pass or not reg_nombre or not reg_negocio:
                            st.warning("Completá todos los campos, por favor.")
                        elif " " in reg_usuario:
                            st.error("❌ El nombre de usuario no puede tener espacios.")
                        elif reg_nueva_pass != reg_confirma_pass:
                            st.error("❌ Las contraseñas no coinciden.")
                        else:
                            # Le pasamos los 4 datos (incluyendo reg_negocio) a la base de datos
                            exito, msj = db.registrar_usuario(reg_usuario, reg_email, reg_nombre, reg_negocio, reg_nueva_pass)
                            if exito:
                                st.success(msj)
                                st.info("Ve a la pestaña 'Ingresar' para iniciar sesión.")
                            else:
                                st.error(msj)
                                
           # --- PESTAÑA RECUPERAR CONTRASEÑA ---
            with tab_recuperar:
                with st.form("recuperar_form"):
                    st.markdown("Ingresá tu correo para crear una nueva contraseña.")
                    # Eliminamos el campo del nombre de usuario
                    rec_email = st.text_input("Tu correo electrónico registrado").lower().strip()
                    rec_nueva_pass = st.text_input("Nueva contraseña", type="password")
                    rec_confirma_pass = st.text_input("Repetir nueva contraseña", type="password")
                    
                    submit_recuperar = st.form_submit_button("Restablecer Contraseña", use_container_width=True)
                    
                    if submit_recuperar:
                        if not rec_email or not rec_nueva_pass:
                            st.warning("Completá todos los campos.")
                        elif rec_nueva_pass != rec_confirma_pass:
                            st.error("❌ Las contraseñas nuevas no coinciden.")
                        else:
                            # Ahora solo le mandamos el email a la base de datos
                            exito, msj = db.recuperar_password(rec_email, rec_nueva_pass)
                            if exito:
                                st.success(msj)
                            else:
                                st.error(msj)

    st.stop() # Frena la carga de la página acá si no hay usuario

# --- 2. ZONA DEL DASHBOARD ---
usuario_actual = st.session_state['usuario_logueado']

col_tit, col_btn = st.columns([8, 2])
with col_tit:
    st.title(f"📊 Resumen de tu negocio, {usuario_actual.capitalize()}")
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        del st.session_state['usuario_logueado']
        st.rerun()

st.markdown("---")

ventas_totales, compras_totales, capital_inventario = db.obtener_kpis(usuario_actual)
flujo_caja = ventas_totales - compras_totales 

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ingresos por Ventas", f"${ventas_totales:,.2f}", "Plata que entró")
col2.metric("Inversión en Compras", f"${compras_totales:,.2f}", "-Plata que salió", delta_color="inverse")
col3.metric("Flujo de Caja", f"${flujo_caja:,.2f}", "Balance neto")
col4.metric("Valor del Inventario", f"${capital_inventario:,.2f}", "Capital en mercadería", delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)

col_grafico, col_ranking = st.columns([6, 4])

with col_grafico:
    st.subheader("📈 Evolución de Ingresos")
    df_ventas_dia = db.obtener_ventas_por_dia(usuario_actual)
    if df_ventas_dia.empty:
        st.info("Todavía no hay suficientes ventas para armar el gráfico.")
    else:
        df_ventas_dia.set_index('fecha', inplace=True)
        st.bar_chart(df_ventas_dia['ingresos'], color="#2e9b5c")

with col_ranking:
    st.subheader("🏆 Top 5 Productos más vendidos")
    df_top_productos = db.obtener_top_productos(usuario_actual)
    if df_top_productos.empty:
        st.info("Aún no hay registros de productos vendidos.")
    else:
        st.dataframe(df_top_productos, use_container_width=True, hide_index=True)