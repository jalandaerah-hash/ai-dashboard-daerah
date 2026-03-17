import streamlit as st
import sqlite3
import pandas as pd
from google import genai
import matplotlib.pyplot as plt

# ==========================================
# 1. KONFIGURASI AI & DATABASE (VERSI STABIL)
# ==========================================
try:
    # Mengambil API Key secara aman dari Secrets Streamlit
    API_KEY = st.secrets["GEMINI_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except KeyError:
    st.error("Kunci API tidak ditemukan. Pastikan Anda telah mengisinya di menu 'Advanced settings -> Secrets' di Streamlit Cloud.")
    st.stop()

# Nama file database lokal Anda
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
# 2. LOGIKA AGEN AI (SQL & VISUALISASI)
# ==========================================
def agen_sql(pertanyaan, schema):
    """Agen 1: Mengubah bahasa manusia menjadi SQL dengan filter pencarian cerdas."""
    prompt = f"""
    Kamu adalah Ahli Database untuk instansi pemerintah.
    Tugasmu membuat query SQL yang valid berdasarkan skema database berikut:
    {schema}
    
    Aturan Keras agar data tidak kosong:
    1. Gunakan JOIN antara dim_wilayah dan tabel fakta menggunakan id_wilayah.
    2. Untuk pencarian Teks (Nama Provinsi, Kabupaten, Kota, Komoditas):
       - JANGAN gunakan tanda sama dengan (=).
       - SELALU gunakan fungsi LOWER() dan LIKE dengan wildcard %.
       - Contoh: LOWER(nama_provinsi) LIKE '%jawa barat%'
    3. Kembalikan HANYA query SQL saja tanpa penjelasan dan tanpa tanda ```sql.
    
    Pertanyaan user: "{pertanyaan}"
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text.replace('```sql', '').replace('```', '').strip()

def agen_visualisasi(dataframe, pertanyaan):
    """Agen 2: Membuat grafik otomatis berdasarkan hasil data."""
    df_sample = dataframe.head(5).to_string()
    columns = list(dataframe.columns)
    
    prompt = f"""
    Kamu adalah Ahli Visualisasi Data Python.
    Dataframe bernama `df` memiliki kolom: {columns}
    Contoh data: {df_sample}
    
    Tugas: Tulis kode Python matplotlib untuk membuat grafik sesuai pertanyaan: "{pertanyaan}"
    Aturan:
    1. Gunakan `fig, ax = plt.subplots(figsize=(10, 6))`.
    2. Putar label X agar tidak tumpang tindih (`plt.xticks(rotation=45)`).
    3. Kembalikan HANYA kode Python saja tanpa markdown.
    """
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text.replace('```python', '').replace('```', '').strip()

# ==========================================
# 3. ANTARMUKA PENGGUNA (STREAMLIT)
# ==========================================
# Pengaturan Judul Baru sesuai permintaan
st.set_page_config(page_title="Chatbot AI Subdit Jalan Daerah", layout="wide")
st.title("🛣️ Chatbot AI Subdit Jalan Daerah")
st.markdown("""
Selamat datang di layanan data mandiri **Subdit Jalan Daerah**. 
Silakan tanyakan informasi mengenai kondisi jalan, keuangan daerah, atau komoditas agrikultur. 
Gunakan kata **'grafik'** untuk visualisasi otomatis.
""")

# Load skema
skema_db = get_database_schema()

# Input Chat
query_user = st.chat_input("Tulis pertanyaan Anda di sini... (Contoh: Tampilkan data jalan di Jawa Barat dan buatkan grafiknya)")

if query_user:
    st.chat_message("user").write(query_user)
    
    with st.chat_message("assistant"):
        with st.spinner("Sedang memproses data..."):
            try:
                # Proses SQL
                sql_query = agen_sql(query_user, skema_db)
                
                with st.expander("🔍 Detail Query SQL"):
                    st.code(sql_query, language="sql")
                
                conn = sqlite3.connect(DB_PATH)
                df_hasil = pd.read_sql_query(sql_query, conn)
                conn.close()
                
                if df_hasil.empty:
                    st.info("Data tidak ditemukan. Coba periksa kembali ejaan nama daerah atau tahun data.")
                else:
                    st.write("**Hasil Data:**")
                    st.dataframe(df_hasil)
                    
                    # Proses Grafik
                    kata_kunci = ['grafik', 'chart', 'plot', 'visual']
                    if any(k in query_user.lower() for k in kata_kunci):
                        with st.spinner("Menyiapkan visualisasi..."):
                            kode_python = agen_visualisasi(df_hasil, query_user)
                            
                            with st.expander("💻 Detail Kode Grafik"):
                                st.code(kode_python, language="python")
                            
                            local_vars = {"df": df_hasil, "plt": plt}
                            exec(kode_python, globals(), local_vars)
                            
                            if 'fig' in local_vars:
                                st.pyplot(local_vars['fig'])
                            else:
                                st.warning("Maaf, AI gagal menyusun grafik untuk data ini.")
                                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    st.warning("⏱️ Server AI sedang sibuk. Mohon tunggu 30 detik lalu coba lagi.")
                else:
                    st.error(f"Terjadi kesalahan teknis: {e}")
