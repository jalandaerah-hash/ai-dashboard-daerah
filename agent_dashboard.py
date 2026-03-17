import streamlit as st
import sqlite3
import pandas as pd
from google import genai
import matplotlib.pyplot as plt

# ==========================================
# 1. KONFIGURASI AI & DATABASE (VERSI CLOUD FINAL)
# ==========================================
try:
    # Membaca API Key dari brankas rahasia Streamlit Cloud
    API_KEY = st.secrets["GEMINI_API_KEY"]
    # Inisialisasi Client standar terbaru Google
    client = genai.Client(api_key=API_KEY)
except KeyError:
    st.error("Kunci API tidak ditemukan. Pastikan Anda telah mengisinya di menu 'Advanced settings -> Secrets' di Streamlit Cloud.")
    st.stop()

# Nama file database SQLite Anda
DB_PATH = 'database_daerah.db'

def get_database_schema():
    """Membaca struktur tabel secara otomatis agar AI memahami konteks data."""
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
    """Agen 1: Menerjemahkan bahasa manusia menjadi query SQL yang presisi."""
    prompt = f"""
    Kamu adalah Ahli Database PostgreSQL dan SQLite tingkat lanjut.
    Tugasmu membuat query SQL yang valid berdasarkan skema database berikut:
    {schema}
    
    Aturan Keras:
    1. Hanya gunakan kolom yang ada di skema. 
    2. Tabel dim_wilayah dan fact_agrikultur/fact_jalan/fact_keuangan dihubungkan dengan id_wilayah.
    3. Selalu gunakan JOIN jika membutuhkan nama wilayah.
    4. KELUARKAN HANYA QUERY SQL-nya saja, tanpa penjelasan, tanpa format markdown ```sql.
    
    Pertanyaan user: "{pertanyaan}"
    """
    # Menggunakan model Gemini 2.0 Flash terbaru
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    return response.text.replace('```sql', '').replace('```', '').strip()

def agen_visualisasi(dataframe, pertanyaan):
    """Agen 2: Membaca hasil data SQL dan menulis kode Python untuk menggambar grafik."""
    # Memberikan sampel data agar AI mengerti isi tabel yang dihasilkan
    df_sample = dataframe.head(5).to_string()
    columns = list(dataframe.columns)
    
    prompt = f"""
    Kamu adalah Data Scientist spesialis visualisasi data dengan Python.
    Saya punya pandas DataFrame bernama `df` dengan kolom: {columns}
    Contoh isi datanya:
    {df_sample}
    
    Pertanyaan/Tujuan user: "{pertanyaan}"
    
    Tugas: Tulis skrip Python menggunakan `matplotlib.pyplot as plt` untuk membuat grafik yang paling cocok (Bar, Line, Pie, dll).
    
    Aturan Keras:
    1. Kode harus mendefinisikan variabel `fig, ax = plt.subplots(figsize=(10, 6))`
    2. Dataframe sudah dimuat dengan nama `df`. Dilarang membuat dummy data.
    3. Putar label sumbu X (rotation=45) agar teks nama daerah yang panjang bisa terbaca.
    4. KELUARKAN HANYA KODE PYTHON-nya saja, tanpa format markdown ```python.
    """
    response = client.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt
    )
    return response.text.replace('```python', '').replace('```', '').strip()

# ==========================================
# 3. ANTARMUKA PENGGUNA (STREAMLIT DASHBOARD)
# ==========================================
# Konfigurasi tampilan halaman web
st.set_page_config(page_title="Dashboard AI Daerah", layout="wide")
st.title("🤖 AI Data Analyst - Infrastruktur & Agrikultur")
st.markdown("Tanyakan apa saja tentang data daerah. Tambahkan instruksi **'buatkan grafik'** jika Anda ingin melihat visualisasi datanya.")

# Memuat skema database ke memori
skema_db = get_database_schema()

# Kotak input obrolan utama
query_user = st.chat_input("Contoh: Tampilkan 5 kabupaten di Jawa Barat dengan jalan mantap terpanjang tahun 2025 beserta grafiknya")

if query_user:
    # Menampilkan pertanyaan user di layar
    st.chat_message("user").write(query_user)
    
    with st.chat_message("assistant"):
        with st.spinner("Menyusun algoritma pencarian data..."):
            try:
                # -----------------------------------------
                # FASE 1: EKSTRAKSI DATA
                # -----------------------------------------
                sql_dihasilkan = agen_sql(query_user, skema_db)
                
                with st.expander("🔍 Lihat Query SQL yang Dihasilkan AI"):
                    st.code(sql_dihasilkan, language="sql")
                
                conn = sqlite3.connect(DB_PATH)
                df_hasil = pd.read_sql_query(sql_dihasilkan, conn)
                conn.close()
                
                st.write("**Hasil Ekstraksi Data:**")
                st.dataframe(df_hasil)
                
                # -----------------------------------------
                # FASE 2: VISUALISASI GRAFIK (Opsional)
                # -----------------------------------------
                kata_kunci = ['grafik', 'chart', 'plot', 'visual']
                if any(kata in query_user.lower() for kata in kata_kunci) and not df_hasil.empty:
                    with st.spinner("Menggambar visualisasi data..."):
                        kode_python = agen_visualisasi(df_hasil, query_user)
                        
                        with st.expander("💻 Lihat Kode Python (Matplotlib)"):
                            st.code(kode_python, language="python")
                        
                        # Mengeksekusi kode Python yang dibuat AI dalam lingkungan tertutup
                        local_vars = {"df": df_hasil, "plt": plt}
                        exec(kode_python, globals(), local_vars)
                        
                        # Menampilkan grafik ke layar jika berhasil dibuat
                        if 'fig' in local_vars:
                            st.pyplot(local_vars['fig'])
                        else:
                            st.warning("Agen gagal merender format gambar yang standar.")
                            
            except Exception as e:
                # Menangkap dan menampilkan error teknis jika ada kesalahan logika AI
                st.error(f"Terjadi kesalahan saat memproses permintaan: {e}")
