import streamlit as st
import sqlite3
import pandas as pd
from google import genai
import matplotlib.pyplot as plt
import time

# ==========================================
# 1. KONFIGURASI AI & DATABASE
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except KeyError:
    st.error("Kunci API tidak ditemukan di Streamlit Secrets.")
    st.stop()

DB_PATH = 'database_daerah.db'

def get_database_schema():
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
        schema_info += f"- Tabel `{table_name}` memiliki kolom: {col_details}\n"
    conn.close()
    return schema_info

# ==========================================
# 2. LOGIKA AGEN AI (DENGAN RECOVRY MODE)
# ==========================================
def agen_sql(pertanyaan, schema):
    prompt = f"""
    Kamu adalah Ahli Database PostgreSQL dan SQLite tingkat lanjut.
    Tugasmu membuat query SQL yang valid berdasarkan skema database berikut:
    {schema}
    
    Aturan Keras:
    1. Hanya gunakan kolom yang ada di skema. 
    2. Tabel dim_wilayah dan fact_agrikultur/fact_jalan/fact_keuangan dihubungkan dengan id_wilayah.
    3. Selalu gunakan JOIN jika membutuhkan nama wilayah.
    4. KELUARKAN HANYA QUERY SQL-nya saja tanpa penjelasan dan tanpa markdown.
    5. Gunakan LOWER() dan LIKE %...% untuk pencarian teks daerah agar lebih akurat.
    
    Pertanyaan user: "{pertanyaan}"
    """
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    return response.text.replace('```sql', '').replace('```', '').strip()

def agen_visualisasi(dataframe, pertanyaan):
    df_sample = dataframe.head(5).to_string()
    columns = list(dataframe.columns)
    
    prompt = f"""
    Kamu adalah Data Scientist spesialis visualisasi data.
    Dataframe bernama `df` memiliki kolom: {columns}
    Contoh data: {df_sample}
    
    Tugas: Tulis kode Python matplotlib untuk membuat grafik sesuai pertanyaan: "{pertanyaan}"
    Aturan:
    1. Gunakan `fig, ax = plt.subplots(figsize=(10, 6))`.
    2. Dataframe sudah dimuat dengan nama `df`.
    3. Putar label X (rotation=45).
    4. KELUARKAN HANYA KODE PYTHON-nya saja tanpa markdown.
    """
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    return response.text.replace('```python', '').replace('```', '').strip()

# ==========================================
# 3. ANTARMUKA PENGGUNA (JUDUL BARU)
# ==========================================
st.set_page_config(page_title="Chatbot AI Subdit Jalan Daerah", layout="wide")
st.title("🛣️ Chatbot AI Subdit Jalan Daerah")
st.markdown("""
Selamat datang di layanan data mandiri **Subdit Jalan Daerah**. 
Silakan tanyakan informasi mengenai kondisi jalan, keuangan daerah, atau agrikultur. 
Gunakan kata **'grafik'** untuk melihat visualisasi data.
""")

skema_db = get_database_schema()
query_user = st.chat_input("Tulis pertanyaan Anda di sini... (Contoh: Tampilkan data jalan di Jawa Barat)")

if query_user:
    st.chat_message("user").write(query_user)
    
    with st.chat_message("assistant"):
        with st.spinner("Menganalisis data..."):
            try:
                # FASE 1: SQL
                sql_dihasilkan = agen_sql(query_user, skema_db)
                
                with st.expander("🔍 Lihat Query SQL"):
                    st.code(sql_dihasilkan, language="sql")
                
                conn = sqlite3.connect(DB_PATH)
                df_hasil = pd.read_sql_query(sql_dihasilkan, conn)
                conn.close()
                
                if df_hasil.empty:
                    st.info("Data tidak ditemukan. Pastikan ejaan nama daerah sudah benar.")
                else:
                    st.write("**Hasil Ekstraksi Data:**")
                    st.dataframe(df_hasil)
                    
                    # FASE 2: GRAFIK (Hanya jika diminta)
                    kata_kunci = ['grafik', 'chart', 'plot', 'visual']
                    if any(kata in query_user.lower() for kata in kata_kunci):
                        # Jeda singkat 2 detik untuk menghindari rate limit antar-request
                        time.sleep(2) 
                        
                        with st.spinner("Menggambar grafik..."):
                            kode_python = agen_visualisasi(df_hasil, query_user)
                            
                            with st.expander("💻 Lihat Kode Grafik"):
                                st.code(kode_python, language="python")
                            
                            local_vars = {"df": df_hasil, "plt": plt}
                            exec(kode_python, globals(), local_vars)
                            
                            if 'fig' in local_vars:
                                st.pyplot(local_vars['fig'])
                            else:
                                st.warning("AI gagal menyusun grafik.")
                            
            except Exception as e:
                pesan_error = str(e)
                if "429" in pesan_error or "RESOURCE_EXHAUSTED" in pesan_error:
                    st.warning("⏱️ Server AI sedang sangat padat. Mohon tunggu 30-60 detik tanpa menekan Enter agar kuota API Anda pulih kembali.")
                else:
                    st.error(f"Terjadi kesalahan teknis: {e}")
