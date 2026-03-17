import streamlit as st
import sqlite3
import pandas as pd
from google import genai
import matplotlib.pyplot as plt
import time

# ==========================================
# 1. KONFIGURASI AI & DATABASE (VERSI STABIL 2026)
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except KeyError:
    st.error("API Key belum diset di Streamlit Secrets.")
    st.stop()

DB_PATH = 'database_daerah.db'

def get_database_schema():
    """Membaca struktur tabel agar AI paham kolom data Anda."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        schema_info = ""
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            col_details = ", ".join([f"{col[1]} ({col[2]})" for col in columns])
            schema_info += f"- Tabel `{table_name}`: {col_details}\n"
        conn.close()
        return schema_info
    except Exception:
        return "Gagal memuat skema database."

# ==========================================
# 2. FUNGSI PANGGIL AI (MENGGUNAKAN MODEL LATEST)
# ==========================================
def panggil_ai(prompt):
    """Memanggil model terbaru yang didukung Free Tier."""
    try:
        # Menggunakan 'gemini-1.5-flash-latest' untuk menghindari error 404
        response = client.models.generate_content(
            model='gemini-1.5-flash-latest', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            st.warning("⏱️ Server Google Padat. Menunggu sebentar...")
            time.sleep(20)
            # Coba sekali lagi
            response = client.models.generate_content(model='gemini-1.5-flash-latest', contents=prompt)
            return response.text
        raise e

# ==========================================
# 3. TAMPILAN DASHBOARD
# ==========================================
st.set_page_config(page_title="Chatbot AI Subdit Jalan Daerah", layout="wide")
st.title("🛣️ Chatbot AI Subdit Jalan Daerah")
st.info("Sistem Analisis Data Jalan, Keuangan, dan Agrikultur Daerah.")

skema_db = get_database_schema()
query_user = st.chat_input("Tulis pertanyaan Anda (Contoh: Berapa panjang jalan mantap di Jawa Barat?)")

if query_user:
    st.chat_message("user").write(query_user)
    
    with st.chat_message("assistant"):
        try:
            # TAHAP 1: SQL GENERATION
            prompt_sql = f"""Buatkan query SQLite (HANYA SQL) untuk: {query_user}. 
            Skema: {skema_db}. 
            Aturan: Gunakan LOWER() dan LIKE %...% untuk teks."""
            
            with st.spinner("Mencari data..."):
                sql_raw = panggil_ai(prompt_sql)
                sql_clean = sql_raw.replace('```sql', '').replace('```', '').strip()
                
                with st.expander("Logika Pencarian"):
                    st.code(sql_clean, language="sql")
                
                conn = sqlite3.connect(DB_PATH)
                df = pd.read_sql_query(sql_clean, conn)
                conn.close()
            
            if df.empty:
                st.warning("Data tidak ditemukan di database.")
            else:
                st.write("**Hasil Data:**")
                st.dataframe(df)
                
                # TAHAP 2: VISUALISASI (Jika diminta)
                if any(k in query_user.lower() for k in ['grafik', 'chart', 'plot', 'visual']):
                    time.sleep(2) # Jeda untuk kestabilan API
                    
                    with st.spinner("Membuat grafik..."):
                        prompt_grafik = f"Tulis kode Python matplotlib (HANYA KODE) untuk df dengan kolom {list(df.columns)}. fig, ax = plt.subplots(). User ingin: {query_user}"
                        kode_raw = panggil_ai(prompt_grafik)
                        kode_clean = kode_raw.replace('```python', '').replace('```', '').strip()
                        
                        local_vars = {"df": df, "plt": plt}
                        exec(kode_clean, globals(), local_vars)
                        st.pyplot(local_vars['fig'])
                        
        except Exception as e:
            st.error(f"Mohon maaf, terjadi kendala teknis: {e}")
