"""
Database connection module for the carbon emissions dashboard.
"""
import os
import psycopg2
from dotenv import load_dotenv

# Try to import streamlit for caching, but allow module to be used without it
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

# Load environment variables from .env file
load_dotenv()

def _create_connection():
    """Internal function to create a new database connection."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            port=os.getenv("DB_PORT", "5432"),
            sslmode='require'
        )
        return conn
    except Exception as e:
        raise Exception(f"Failed to connect to database: {e}")

if HAS_STREAMLIT:
    @st.cache_resource
    def get_connection():
        """
        Get a PostgreSQL connection.
        Uses Streamlit's cache_resource to maintain a single connection across reruns.
        """
        return _create_connection()
else:
    def get_connection():
        """
        Get a PostgreSQL connection.
        """
        return _create_connection()

def test_connection():
    """
    Test the database connection by running a simple query.
    Returns:
        tuple: (bool, str) - (Success status, Message or version info)
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        cursor.close()
        return True, f"Connected successfully! PostgreSQL version: {version[0]}"
    except Exception as e:
        return False, str(e)
