# utils/db_connection.py
import psycopg2
import streamlit as st

@st.cache_resource
def init_connection():
    """Establece y mantiene la conexión a la base de datos de Neon."""
    return psycopg2.connect(
        host=st.secrets["neon"]["host"],
        port=st.secrets["neon"]["port"],
        database=st.secrets["neon"]["database"],
        user=st.secrets["neon"]["user"],
        password=st.secrets["neon"]["password"]
    )