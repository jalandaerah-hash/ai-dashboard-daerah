import streamlit as st
import sqlite3
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt

# ==========================================
# 1. KONFIGURASI AI & DATABASE (VERSI CLOUD)
# ==========================================
# Mengambil API Key secara aman dari "brankas rahasia" Streamlit Cloud
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=API_KEY)
except KeyError:
    st.error("Kunci API tidak ditemukan. Pastikan Anda telah mengisinya di menu 'Advanced settings -> Secrets' di Streamlit Cloud.")
    st.stop()

# Menggunakan model AI yang cepat untuk Text-to-SQL
model = genai.GenerativeModel('gemini-1.5-flash')
DB_PATH = 'database_daerah.db'

def get_database_schema():
    """Membaca struktur tabel secara otomatis."""
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
# 2. LOGIKA AGEN AI (MULTI-STEP REASONING)
# ==========================================
def agen_sql(pertanyaan, schema):
    """Agen 1: Ekstraksi Data."""
    prompt = f"""
    Kamu adalah Ahli Database PostgreSQL dan SQLite.
    Tugasmu membuat query SQL yang valid berdasarkan skema database berikut:
    {schema}
    
    Aturan Keras:
    1. Hanya gunakan kolom yang ada di skema. 
    2. Tabel dim_wilayah dan fact_agrikultur/fact_jalan/fact_keuangan dihubungkan dengan id_wilayah.
    3. Selalu gunakan JOIN jika membutuhkan nama wilayah.
    4. KELUARKAN HANYA QUERY SQL-nya saja, tanpa penjelasan, tanpa format markdown ```sql.
    
    Pertanyaan user: "{pertanyaan}"
    """
    response = model.generate_content(prompt)
    return response.text.replace('```sql', '').replace('```', '').strip()

def agen_visualisasi(dataframe, pertanyaan):
    """Agen 2: Rendering Grafik."""
    df_sample = dataframe.head(5).to_string()
    columns = list(dataframe.columns)
    
    prompt = f"""
    Kamu adalah Data Scientist (Python).
    Saya punya pandas DataFrame bernama `df` dengan kolom: {columns}
    Contoh isi datanya:
    {df_sample}
    
    Pertanyaan/Tujuan user: "{pertanyaan}"
    
    Tugas: Tulis skrip Python menggunakan `matplotlib.pyplot as plt` untuk membuat grafik.
    Aturan Keras:
    1. Kode harus mendefinisikan variabel `fig, ax = plt.subplots(figsize=(10, 6))`
    2. Dataframe sudah dimuat dengan nama `df`. Dilarang membuat dummy data.
    3. Putar label sumbu X (rotation=45) agar teks panjang terbaca.
    4. KELUARKAN HANYA KODE PYTHON-nya saja, tanpa format markdown ```python.
    """
    response = model.generate_content(prompt)
    return response.text.replace('```python', '').replace('```', '').strip()

# ==========================================
# 3. ANTARMUKA PENGGUNA (DASHBOARD)
# ==========================================
st.set_page_config(page_title="Dashboard AI Daerah", layout="wide")
st.title("🤖 AI Data Analyst - Infrastruktur & Agrikultur")
st.markdown("Tanyakan apa saja tentang data daerah. Tambahkan kata **'buatkan grafik'** jika ingin melihat visualisasi.")

skema_db = get_database_schema()
query_user = st.chat_input("Contoh: Tampilkan 5 kabupaten di Jawa Barat dengan jalan mantap terpanjang tahun 2025 beserta grafiknya")

if query_user:
    st.chat_message("user").write(query_user)
    
    with st.chat_message("assistant"):
        with st.spinner("Menyusun algoritma pencarian..."):
            try:
                # Eksekusi SQL
                sql_dihasilkan = agen_sql(query_user, skema_db)
                with st.expander("🔍 Lihat Query SQL"):
                    st.code(sql_dihasilkan, language="sql")
                
                conn = sqlite3.connect(DB_PATH)
                df_hasil = pd.read_sql_query(sql_dihasilkan, conn)
                conn.close()
                
                st.write("**Hasil Ekstraksi Data:**")
                st.dataframe(df_hasil)
                
                # Eksekusi Grafik jika diminta
                kata_kunci = ['grafik', 'chart', 'plot', 'visual']
                if any(kata in query_user.lower() for kata in kata_kunci) and not df_hasil.empty:
                    with st.spinner("Menggambar visualisasi..."):
                        kode_python = agen_visualisasi(df_hasil, query_user)
                        with st.expander("💻 Lihat Kode Python"):
                            st.code(kode_python, language="python")
                        
                        local_vars = {"df": df_hasil, "plt": plt}
                        exec(kode_python, globals(), local_vars)
                        
                        if 'fig' in local_vars:
                            st.pyplot(local_vars['fig'])
                        else:
                            st.warning("Format gambar tidak terdefinisi standar.")
                            
            except Exception as e:
                st.error(f"Terjadi kesalahan: {e}")