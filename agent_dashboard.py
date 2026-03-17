import streamlit as st
import sqlite3
import pandas as pd
from google import genai
import matplotlib.pyplot as plt
import time

# ==========================================
# 1. KONFIGURASI UTAMA
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except KeyError:
    st.error("API Key belum diset di Streamlit Secrets.")
    st.stop()

DB_PATH = 'database_daerah.db'

def get_database_schema():
    """Fungsi untuk membaca struktur database Anda."""
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
        return "Database tidak ditemukan."

# ==========================================
# 2. LOGIKA AI (MENGGUNAKAN 2.0 FLASH)
# ==========================================
def panggil_ai(prompt):
    """Fungsi panggil AI dengan jeda otomatis untuk menghindari 'Server Sibuk'."""
    try:
        # Kita kembali ke 2.0-flash karena ini yang paling lancar di akun Anda
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt
        )
        return response.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            # Jika sibuk, paksa sistem menunggu 30 detik
            st.toast("⚠️ Server sibuk, menunggu 30 detik agar kuota pulih...")
            time.sleep(30)
            # Coba sekali lagi
            response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            return response.text
        raise e

# ==========================================
# 3. ANTARMUKA PENGGUNA
# ==========================================
st.set_page_config(page_title="Chatbot AI Subdit Jalan Daerah", layout="wide")
st.title("🛣️ Chatbot AI Subdit Jalan Daerah")
st.markdown("Analisis data jalan dan infrastruktur daerah secara otomatis.")

skema_db = get_database_schema()
query_user = st.chat_input("Contoh: Tampilkan panjang jalan mantap di Jawa Barat tahun 2025")

if query_user:
    st.chat_message("user").write(query_user)
    
    with st.chat_message("assistant"):
        try:
            # TAHAP 1: GENERATE SQL
            prompt_sql = f"""Buat query SQL (HANYA SQL) untuk skema: {skema_db}. 
            Pertanyaan: {query_user}. 
            Aturan: Gunakan LOWER() dan LIKE %...% untuk teks daerah."""
            
            with st.spinner("Mencari data di Subdit..."):
                sql_raw = panggil_ai(prompt_sql)
                sql_clean = sql_raw.replace('```sql', '').replace('```', '').strip()
                
                with st.expander("Detail Analisis SQL"):
                    st.code(sql_clean, language="sql")
                
                conn = sqlite3.connect(DB_PATH)
                df = pd.read_sql_query(sql_clean, conn)
                conn.close()
            
            if df.empty:
                st.warning("Data tidak ditemukan. Pastikan ejaan nama daerah sudah benar.")
            else:
                st.write("**Data ditemukan:**")
                st.dataframe(df)
                
                # TAHAP 2: GRAFIK (Hanya jika ada kata kunci grafik)
                if any(k in query_user.lower() for k in ['grafik', 'chart', 'plot', 'visual']):
                    # Jeda paksa 3 detik antar permintaan agar tidak terkena limit
                    time.sleep(3)
                    
                    with st.spinner("Membuat visualisasi..."):
                        prompt_grafik = f"Buat kode matplotlib (HANYA KODE) untuk df dengan kolom {list(df.columns)}. fig, ax = plt.subplots(). User ingin: {query_user}"
                        kode_raw = panggil_ai(prompt_grafik)
                        kode_clean = kode_raw.replace('```python', '').replace('```', '').strip()
                        
                        local_vars = {"df": df, "plt": plt}
                        exec(kode_clean, globals(), local_vars)
                        st.pyplot(local_vars['fig'])
                        
        except Exception as e:
            st.error(f"Mohon maaf, terjadi kendala teknis: {e}")
