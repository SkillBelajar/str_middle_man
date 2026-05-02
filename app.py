import streamlit as st
import sqlite3
import hashlib
import pandas as pd
import requests

# ==========================================
# 1. DATABASE INITIALIZATION & FUNCTIONS
# ==========================================
DB_NAME = "reseller_app.db"

def init_db():
    """Membuat tabel database jika belum ada."""
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    c = conn.cursor()
    
    # Tabel Users
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Tabel User Settings (Untuk API Key OpenRouter)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            api_key TEXT,
            preferred_model TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # Tabel Main Data (Katalog Barang / Inventory)
    c.execute('''
        CREATE TABLE IF NOT EXISTS main_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            supplier_price REAL DEFAULT 0,
            selling_price REAL DEFAULT 0,
            stock INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # --- TAMBAHAN SPRINT 2 TASK 3: Tabel AI Reports ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS ai_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            report_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # --- TAMBAHAN SPRINT 3 TASK 1: Tabel Transaksi Penjualan ---
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            customer_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            profit_earned REAL NOT NULL,
            transaction_date DATE NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(product_id) REFERENCES main_data(id)
        )
    ''')

    conn.commit()
    conn.close()

# Inisialisasi DB saat aplikasi pertama kali dijalankan
init_db()

def add_item(user_id, item_name, supplier_price, selling_price, stock):
    """Menambah barang baru ke database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO main_data (user_id, item_name, supplier_price, selling_price, stock) VALUES (?, ?, ?, ?, ?)",
              (user_id, item_name, supplier_price, selling_price, stock))
    conn.commit()
    conn.close()

def get_items(user_id):
    """Mengambil data barang milik user tertentu"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT id, item_name as 'Nama Barang', supplier_price as 'Harga Modal', selling_price as 'Harga Jual', stock as 'Stok' FROM main_data WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def delete_item(item_id):
    """Menghapus barang berdasarkan ID"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM main_data WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

def update_item(item_id, item_name, supplier_price, selling_price, stock):
    """Mengupdate data barang"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE main_data SET item_name = ?, supplier_price = ?, selling_price = ?, stock = ? WHERE id = ?",
              (item_name, supplier_price, selling_price, stock, item_id))
    conn.commit()
    conn.close()

# --- TAMBAHAN SPRINT 3 TASK 1: FUNGSI TRANSAKSI & CRM ---
import datetime

def record_sale(user_id, product_id, customer_name, qty, date):
    """Mencatat penjualan, memotong stok, dan menghitung profit otomatis"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Cek harga dan stok barang saat ini
    c.execute("SELECT supplier_price, selling_price, stock FROM main_data WHERE id = ?", (product_id,))
    prod = c.fetchone()
    
    if prod and prod[2] >= qty:
        # Hitung profit: (Harga Jual - Harga Modal) * Kuantitas Terjual
        profit = (prod[1] - prod[0]) * qty
        new_stock = prod[2] - qty
        
        # 1. Potong stok di tabel main_data
        c.execute("UPDATE main_data SET stock = ? WHERE id = ?", (new_stock, product_id))
        
        # 2. Catat riwayat di tabel transactions
        c.execute("INSERT INTO transactions (user_id, product_id, customer_name, qty, profit_earned, transaction_date) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, product_id, customer_name, qty, profit, date))
        conn.commit()
        res = True
    else:
        res = False # Stok tidak cukup atau barang tidak ditemukan
        
    conn.close()
    return res

def get_transactions(user_id):
    """Mengambil data riwayat penjualan user"""
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT t.transaction_date as 'Tanggal', m.item_name as 'Barang', t.customer_name as 'Pelanggan', 
               t.qty as 'Jumlah', t.profit_earned as 'Profit Bersih'
        FROM transactions t
        JOIN main_data m ON t.product_id = m.id
        WHERE t.user_id = ?
        ORDER BY t.transaction_date DESC, t.id DESC
    """
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df

# --- TAMBAHAN SPRINT 2: FUNGSI USER SETTINGS ---
def get_user_settings(user_id):
    """Mengambil setting API Key dan Model AI untuk user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT api_key, preferred_model FROM user_settings WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result

def update_user_settings(user_id, api_key, preferred_model):
    """Menyimpan atau mengupdate setting AI user"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id FROM user_settings WHERE user_id = ?", (user_id,))
    if c.fetchone():
        c.execute("UPDATE user_settings SET api_key = ?, preferred_model = ? WHERE user_id = ?", (api_key, preferred_model, user_id))
    else:
        c.execute("INSERT INTO user_settings (user_id, api_key, preferred_model) VALUES (?, ?, ?)", (user_id, api_key, preferred_model))
    conn.commit()
    conn.close()

# --- TAMBAHAN SPRINT 2 TASK 3: FUNGSI HISTORY AI ---
def save_ai_report(user_id, report_text):
    """Menyimpan hasil analisis AI ke database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO ai_reports (user_id, report_text) VALUES (?, ?)", (user_id, report_text))
    conn.commit()
    conn.close()

def get_ai_reports(user_id):
    """Mengambil riwayat analisis AI"""
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT created_at as Tanggal, report_text as Hasil_Analisis FROM ai_reports WHERE user_id = ? ORDER BY created_at DESC", conn, params=(user_id,))
    conn.close()
    return df

# --- TAMBAHAN SPRINT 2: FUNGSI OPENROUTER AI ---
def get_ai_insight(api_key, model, df):
    """Mengirim data ringkasan ke OpenRouter dan mendapatkan insight bisnis"""
    if not api_key:
        return "⚠️ Error: API Key OpenRouter belum diatur. Silakan isi di menu Settings."
    
    if df.empty:
        return "💡 Data inventory masih kosong. Tambahkan barang terlebih dahulu agar AI bisa menganalisis."

    # Prompt Strategy: Memilih kolom penting dan merangkumnya
    df['Margin (%)'] = ((df['Harga Jual'] - df['Harga Modal']) / df['Harga Modal'] * 100).round(1)
    df['Potensi Profit'] = (df['Harga Jual'] - df['Harga Modal']) * df['Stok']
    
    # PERBAIKAN: Menggunakan .to_string() yang merupakan bawaan murni Pandas (tanpa perlu library tabulate)
    data_str = df[['Nama Barang', 'Stok', 'Margin (%)', 'Potensi Profit']].to_string(index=False)
    
    prompt = f"""
    Sebagai pakar bisnis dan konsultan reseller, analisis data inventory berikut:
    
    {data_str}
    
    Tugas Anda:
    1. Identifikasi 1-2 barang dengan "Potensi Profit" terbaik yang harus digenjot penjualannya.
    2. Beri peringatan jika ada barang dengan stok mati/menipis.
    3. Berikan 1 strategi singkat (maksimal 2 kalimat) untuk memaksimalkan keuntungan dari data di atas.
    
    Gunakan bahasa Indonesia yang profesional, ramah, dan ringkas. Jangan terlalu panjang.
    """

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Anda adalah asisten konsultan bisnis yang cerdas dan praktis."},
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"❌ Terjadi kesalahan saat menghubungi AI: {str(e)}"

# ==========================================
# 2. AUTHENTICATION FUNCTIONS
# ==========================================
def hash_password(password):
    """Mengamankan password menggunakan SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    """Mendaftarkan user baru ke database"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username sudah ada
    finally:
        conn.close()

def login_user(username, password):
    """Mengecek kredensial login"""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, hash_password(password)))
    user = c.fetchone()
    conn.close()
    return user # Mengembalikan (id, username) jika sukses, None jika gagal

# ==========================================
# 3. SESSION STATE INITIALIZATION
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = ""

# ==========================================
# 4. UI LAYOUT & ROUTER
# ==========================================
st.set_page_config(page_title="Reseller Intelligence App", page_icon="📦", layout="wide")

# -- SIDEBAR --
with st.sidebar:
    st.title("📦 Reseller AI System")
    st.markdown("---")
    
    if not st.session_state.logged_in:
        st.write("Silakan Login atau Register")
    else:
        st.success(f"Masuk sebagai: **{st.session_state.username}**")
        
        # --- UPDATE MENU NAVIGASI ---
        st.session_state.page = st.radio("Menu Navigasi", ["Dashboard", "Inventory", "CRM & Penjualan", "Konsultan AI", "Settings"])
        st.markdown("---")
        
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.session_state.username = ""
            st.rerun()

# -- MAIN AREA --
st.title("Sistem Manajemen & Analisis Data")

if not st.session_state.logged_in:
    # Tampilan jika belum login (Tab Login / Register)
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login Akun")
        log_username = st.text_input("Username", key="log_user")
        log_password = st.text_input("Password", type="password", key="log_pass")
        if st.button("Login"):
            user = login_user(log_username, log_password)
            if user:
                st.session_state.logged_in = True
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]
                st.success("Login berhasil!")
                st.rerun()
            else:
                st.error("Username atau Password salah!")
                
    with tab2:
        st.subheader("Daftar Akun Baru")
        reg_username = st.text_input("Username Baru", key="reg_user")
        reg_password = st.text_input("Password Baru", type="password", key="reg_pass")
        if st.button("Register"):
            if reg_username and reg_password:
                if register_user(reg_username, reg_password):
                    st.success("Akun berhasil dibuat! Silakan login di tab sebelahnya.")
                else:
                    st.error("Username sudah digunakan. Pilih yang lain.")
            else:
                st.warning("Username dan Password tidak boleh kosong!")

else:
    # Tampilan jika sudah login - Routing berdasarkan Menu Navigasi
    page = st.session_state.get('page', 'Dashboard')
    
    if page == "Dashboard":
        st.write(f"Halo, **{st.session_state.username}**! Selamat datang di dashboard utama Anda.")
        
        # --- PERBARUAN FINAL SPRINT 3: DASHBOARD METRICS (REAL-TIME) ---
        st.subheader("📊 Ringkasan Bisnis Saat Ini")
        
        df_items = get_items(st.session_state.user_id)
        df_trans = get_transactions(st.session_state.user_id)
        
        # Kalkulasi Inventory
        total_barang = len(df_items) if not df_items.empty else 0
        total_stok = int(df_items['Stok'].sum()) if not df_items.empty else 0
        
        # Kalkulasi Penjualan
        total_terjual = int(df_trans['Jumlah'].sum()) if not df_trans.empty else 0
        total_profit_bersih = float(df_trans['Profit Bersih'].sum()) if not df_trans.empty else 0.0
        
        # Tampilkan Metrik 4 Kolom
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📦 Jenis Barang", f"{total_barang} item")
        col2.metric("📊 Sisa Stok", f"{total_stok} pcs")
        col3.metric("🛒 Total Terjual", f"{total_terjual} pcs")
        col4.metric("💰 Profit Bersih", f"Rp {total_profit_bersih:,.0f}")
        
        st.markdown("---")
        
        # Tampilkan 5 Transaksi Terakhir di Dashboard
        st.subheader("📜 5 Transaksi Terakhir")
        if not df_trans.empty:
            st.dataframe(df_trans.head(5), use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada transaksi penjualan. Mulai catat penjualan di menu 'CRM & Penjualan'.")
        
        st.markdown("---")
        # Ping Feature sesuai permintaan
        st.info("🟢 System Ready")
        st.write("Database SQLite terhubung, AI siap digunakan, dan sistem transaksi aktif.")
        
    elif page == "Inventory":
        st.header("📦 Manajemen Inventory")
        
        # Form Tambah Data
        with st.expander("➕ Tambah Barang Baru", expanded=True):
            with st.form("form_tambah_barang", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    nama_barang = st.text_input("Nama Barang")
                    stok = st.number_input("Stok Awal", min_value=0, step=1)
                with col2:
                    harga_modal = st.number_input("Harga Modal (Supplier)", min_value=0.0, step=1000.0)
                    harga_jual = st.number_input("Harga Jual", min_value=0.0, step=1000.0)
                    
                submit_add = st.form_submit_button("Simpan Barang")
                if submit_add:
                    if nama_barang:
                        add_item(st.session_state.user_id, nama_barang, harga_modal, harga_jual, stok)
                        st.success(f"Barang '{nama_barang}' berhasil ditambahkan!")
                        st.rerun()
                    else:
                        st.error("Nama barang tidak boleh kosong!")
        
        # Tabel Data & Hapus
        st.subheader("Daftar Barang Anda")
        df_items = get_items(st.session_state.user_id)
        
        if df_items.empty:
            st.info("Belum ada data barang. Silakan tambahkan di atas.")
        else:
            # Menampilkan data tabel
            st.dataframe(df_items, use_container_width=True, hide_index=True)
            
            # Fitur Edit dan Hapus Data
            st.markdown("---")
            st.subheader("⚙️ Edit atau Hapus Barang")
            
            item_to_manage = st.selectbox("Pilih barang untuk dikelola:", df_items['Nama Barang'].tolist())
            selected_row = df_items[df_items['Nama Barang'] == item_to_manage].iloc[0]
            item_id = int(selected_row['id'])
            
            tab_edit, tab_del = st.tabs(["✏️ Edit Data", "🗑️ Hapus Data"])
            
            with tab_edit:
                with st.form("form_edit_barang"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        e_nama = st.text_input("Nama Barang", value=selected_row['Nama Barang'])
                        e_stok = st.number_input("Stok", min_value=0, step=1, value=int(selected_row['Stok']))
                    with e_col2:
                        e_modal = st.number_input("Harga Modal", min_value=0.0, step=1000.0, value=float(selected_row['Harga Modal']))
                        e_jual = st.number_input("Harga Jual", min_value=0.0, step=1000.0, value=float(selected_row['Harga Jual']))
                    
                    if st.form_submit_button("Update Barang"):
                        update_item(item_id, e_nama, e_modal, e_jual, e_stok)
                        st.success(f"Data '{e_nama}' berhasil diupdate!")
                        st.rerun()

            with tab_del:
                st.warning(f"Tindakan ini akan menghapus '{item_to_manage}' secara permanen.")
                if st.button("Ya, Hapus Barang", type="primary"):
                    delete_item(item_id)
                    st.success(f"Barang '{item_to_manage}' telah dihapus.")
                    st.rerun()

    # --- TAMBAHAN SPRINT 3 TASK 1: MENU CRM & PENJUALAN ---
    elif page == "CRM & Penjualan":
        st.header("🤝 CRM & Catat Penjualan")
        st.write("Catat setiap barang yang laku di sini. Stok akan terpotong otomatis dan profit akan dihitung.")
        
        df_items = get_items(st.session_state.user_id)
        
        if df_items.empty:
            st.warning("Anda belum memiliki barang di Inventory. Silakan tambah barang terlebih dahulu.")
        else:
            with st.form("form_penjualan", clear_on_submit=True):
                st.subheader("📝 Input Penjualan Baru")
                
                # Buat dictionary untuk mapping nama barang ke ID
                item_dict = dict(zip(df_items['Nama Barang'], df_items['id']))
                
                col1, col2 = st.columns(2)
                with col1:
                    t_tanggal = st.date_input("Tanggal Penjualan", datetime.date.today())
                    t_barang = st.selectbox("Pilih Barang Terjual", list(item_dict.keys()))
                with col2:
                    t_pelanggan = st.text_input("Nama Pelanggan (CRM)")
                    t_qty = st.number_input("Jumlah Terjual (Qty)", min_value=1, step=1)
                    
                if st.form_submit_button("Catat Penjualan"):
                    if t_pelanggan:
                        product_id = item_dict[t_barang]
                        sukses = record_sale(st.session_state.user_id, product_id, t_pelanggan, t_qty, t_tanggal)
                        if sukses:
                            st.success(f"Berhasil! Penjualan ke {t_pelanggan} telah dicatat. Stok terpotong otomatis.")
                            st.rerun()
                        else:
                            st.error("Gagal! Stok barang tidak mencukupi untuk jumlah penjualan ini.")
                    else:
                        st.error("Nama Pelanggan tidak boleh kosong!")
            
            st.markdown("---")
            st.subheader("📜 Riwayat Penjualan Anda")
            df_trans = get_transactions(st.session_state.user_id)
            if df_trans.empty:
                st.info("Belum ada data penjualan.")
            else:
                st.dataframe(df_trans, use_container_width=True, hide_index=True)

    # --- TAMBAHAN SPRINT 2: MENU KONSULTAN AI ---
    elif page == "Konsultan AI":
        st.header("🤖 Konsultan Bisnis AI")
        st.write("Dapatkan insight otomatis dan rekomendasi penjualan berdasarkan data inventory Anda.")
        
        settings = get_user_settings(st.session_state.user_id)
        api_key = settings[0] if settings else ""
        model = settings[1] if settings else ""
        
        if not api_key:
            st.warning("⚠️ Anda belum memasukkan API Key OpenRouter. Silakan ke menu **Settings**.")
        else:
            st.info(f"Model AI yang digunakan: **{model}**")
            
            df_items = get_items(st.session_state.user_id)
            
            # Menampilkan preview data yang akan dikirim ke AI
            with st.expander("Lihat Data yang akan dianalisis"):
                if not df_items.empty:
                    st.dataframe(df_items[['Nama Barang', 'Harga Modal', 'Harga Jual', 'Stok']], hide_index=True)
                else:
                    st.write("Data kosong.")
            
            if st.button("🧠 Generate Insight Bisnis", type="primary"):
                with st.spinner("AI sedang menganalisis data Anda..."):
                    insight_result = get_ai_insight(api_key, model, df_items)
                    
                    # Simpan ke DB hanya jika tidak ada error/warning
                    if not insight_result.startswith("⚠️") and not insight_result.startswith("💡") and not insight_result.startswith("❌"):
                        save_ai_report(st.session_state.user_id, insight_result)
                        
                    st.markdown("### 📊 Hasil Analisis AI (Terbaru)")
                    st.success(insight_result)
            
            # --- TAMBAHAN SPRINT 2 TASK 3: UI HISTORY AI ---
            st.markdown("---")
            st.subheader("📚 Riwayat Analisis Sebelumnya")
            df_history = get_ai_reports(st.session_state.user_id)
            
            if df_history.empty:
                st.info("Belum ada riwayat analisis. Silakan generate insight pertama Anda.")
            else:
                for index, row in df_history.iterrows():
                    with st.expander(f"Analisis Tanggal: {row['Tanggal']}"):
                        st.markdown(row['Hasil_Analisis'])

    # --- TAMBAHAN SPRINT 2: MENU SETTINGS ---
    elif page == "Settings":
        st.header("⚙️ Pengaturan AI & OpenRouter")
        st.write("Masukkan API Key OpenRouter Anda untuk mengaktifkan fitur konsultan AI.")
        
        # Ambil data setting saat ini
        settings = get_user_settings(st.session_state.user_id)
        current_api_key = settings[0] if settings else ""
        current_model = settings[1] if settings else "openai/gpt-3.5-turbo"
        
        with st.form("form_settings"):
            st.info("API Key Anda disimpan dengan aman di database lokal SQLite.")
            new_api_key = st.text_input("OpenRouter API Key", value=current_api_key, type="password", help="Dapatkan dari openrouter.ai")
            
            models_list = [
                "openai/gpt-3.5-turbo", 
                "google/gemini-flash-1.5", 
                "meta-llama/llama-3-8b-instruct", 
                "anthropic/claude-3-haiku"
            ]
            
            # Memastikan model yang tersimpan ada di list, jika tidak default ke index 0
            try:
                model_index = models_list.index(current_model)
            except ValueError:
                model_index = 0
                
            new_model = st.selectbox("Pilih Model AI", models_list, index=model_index)
            
            if st.form_submit_button("Simpan Pengaturan"):
                update_user_settings(st.session_state.user_id, new_api_key, new_model)
                st.success("Pengaturan berhasil disimpan!")
                st.rerun()