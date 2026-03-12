import streamlit as st

def requerir_login():
    # Verificamos si la llave 'usuario_logueado' existe y tiene información
    if 'usuario_logueado' not in st.session_state or not st.session_state['usuario_logueado']:
        st.warning("⚠️ Por favor, iniciá sesión en la página de Inicio para acceder a este módulo.")
        st.stop() # Frena la ejecución de la página si no está logueado