import os
import sqlite3
import pymysql
import logging
# pyrefly: ignore [missing-import]
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
# pyrefly: ignore [missing-import]
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Ganti dengan token bot Anda (membaca dari environment jika ada)
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8680524895:AAHVUJfnecsJkCUeHd2V8HrSIZYv1BKLNCw')

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Database Helper Functions ---

DB_TYPE = os.environ.get('DB_TYPE', 'sqlite').lower()
PLACEHOLDER = '%s' if DB_TYPE == 'mysql' else '?'

def get_db_connection():
    if DB_TYPE == 'mysql':
        host = os.environ.get('DB_HOST', 'localhost')
        port = int(os.environ.get('DB_PORT', 3306))
        user = os.environ.get('DB_USER', 'botuser')
        password = os.environ.get('DB_PASSWORD', 'botpassword')
        database = os.environ.get('DB_DATABASE', 'botsite')
        
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
        return conn
    else:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn

def get_unique_column_values(column_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT {column_name} FROM customers WHERE {column_name} IS NOT NULL AND {column_name} != '' ORDER BY {column_name}")
        values = [row[column_name] for row in cursor.fetchall()]
        conn.close()
        return values
    except Exception as e:
        logger.error(f"Error reading {column_name}: {e}")
        return []

def get_unique_branches():
    return get_unique_column_values('Branch')

def get_unique_clusters():
    return get_unique_column_values('Cluster')

def get_unique_clusters_by_branch(branch_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT Cluster FROM customers WHERE Branch = {PLACEHOLDER} AND Cluster IS NOT NULL AND Cluster != '' ORDER BY Cluster",
            (branch_name,)
        )
        values = [row['Cluster'] for row in cursor.fetchall()]
        conn.close()
        return values
    except Exception as e:
        logger.error(f"Error reading clusters for branch {branch_name}: {e}")
        return []

def get_site_ids_by_branch_and_cluster(branch_name, cluster_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT Nearest_Site_ID FROM customers WHERE Branch = {PLACEHOLDER} AND Cluster = {PLACEHOLDER} AND Nearest_Site_ID IS NOT NULL AND Nearest_Site_ID != '' ORDER BY Nearest_Site_ID",
            (branch_name, cluster_name)
        )
        site_ids = [row['Nearest_Site_ID'] for row in cursor.fetchall()]
        conn.close()
        return site_ids
    except Exception as e:
        logger.error(f"Error reading sites by branch {branch_name} and cluster {cluster_name}: {e}")
        return []

def get_site_ids_by_filter(filter_col, filter_val):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT Nearest_Site_ID FROM customers WHERE {filter_col} = {PLACEHOLDER} AND Nearest_Site_ID IS NOT NULL AND Nearest_Site_ID != '' ORDER BY Nearest_Site_ID",
            (filter_val,)
        )
        site_ids = [row['Nearest_Site_ID'] for row in cursor.fetchall()]
        conn.close()
        return site_ids
    except Exception as e:
        logger.error(f"Error reading sites by {filter_col}: {e}")
        return []

def get_site_ids_by_branch(branch_name):
    return get_site_ids_by_filter('Branch', branch_name)

def get_site_ids_by_cluster(cluster_name):
    return get_site_ids_by_filter('Cluster', cluster_name)

def get_customers_by_site_id(site_id):
    customers = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # Hanya ambil data pelanggan yang status Acq-nya bukan 'Y'
        cursor.execute(
            f"SELECT * FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER} AND (Acq IS NULL OR UPPER(TRIM(Acq)) != 'Y')",
            (site_id,)
        )
        customers = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        logger.error(f"Error reading customers by site: {e}")
    return customers

def update_db_acq(bb_id, acq_val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE customers SET Acq = {PLACEHOLDER} WHERE bb_id = {PLACEHOLDER}", (acq_val, bb_id))
    conn.commit()
    conn.close()

def update_db_perdana(bb_id, perdana_val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE customers SET Acq = 'Y', nomor_baru_pelanggan = {PLACEHOLDER} WHERE bb_id = {PLACEHOLDER}", (perdana_val, bb_id))
    conn.commit()
    conn.close()


# --- Keyboard Markup Helpers ---

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏢 Branch", callback_data="menu:branch")],
        [InlineKeyboardButton("🌐 Cluster", callback_data="menu:cluster")],
        [InlineKeyboardButton("📍 Site ID", callback_data="menu:site")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_grid_keyboard(items, callback_prefix, cols=2, back_callback="menu:main"):
    keyboard = []
    for i in range(0, len(items), cols):
        row = [InlineKeyboardButton(item, callback_data=f"{callback_prefix}:{item}") for item in items[i:i+cols]]
        keyboard.append(row)
    if back_callback:
        keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data=back_callback)])
    return InlineKeyboardMarkup(keyboard)

def branch_keyboard():
    return create_grid_keyboard(get_unique_branches(), "branch", back_callback=None)

def cluster_keyboard():
    return create_grid_keyboard(get_unique_clusters(), "cluster")

def sites_keyboard(sites, back_callback):
    return create_grid_keyboard(sites, "site_id", cols=3, back_callback=back_callback)

def acq_keyboard(bb_id):
    keyboard = [
        [
            InlineKeyboardButton("Ya (Y)", callback_data=f"acq:Y:{bb_id}"),
            InlineKeyboardButton("Tidak (N)", callback_data=f"acq:N:{bb_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Customer Display Helpers ---

def format_customer_message(row, index, prompt):
    if not row:
        return prompt
    return (
        f"No: {index + 1}\n"
        f"SITE_ID: {row.get('Nearest_Site_ID', '')}\n"
        f"Nomor IH: {row.get('bb_id', '')}\n"
        f"Nomor HP: {row.get('No_HP', '')}\n"
        f"Nama Pelanggan: {row.get('Nama', '')}\n"
        f"Branch: {row.get('Branch', '')}\n"
        f"Cluster: {row.get('Cluster', '')}\n"
        f"Alamat: {row.get('Alamat', '')}\n"
        f"Kodepos: {row.get('Kodepos', '')}\n\n"
        f"{prompt}"
    )

async def show_customer_for_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('current_index', 0)
    if not results or index >= len(results):
        await update.message.reply_text("Tidak ada data pelanggan untuk SITE ID ini.")
        return
    row = results[index]
    text = format_customer_message(row, index, "Apakah Pelanggan bersedia ganti kartu?")
    await update.message.reply_text(text, reply_markup=acq_keyboard(row.get('bb_id', '')))

async def show_customer_for_query(query, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('current_index', 0)
    if not results or index >= len(results):
        await query.edit_message_text("Tidak ada data pelanggan untuk SITE ID ini.")
        return
    row = results[index]
    text = format_customer_message(row, index, "Apakah Pelanggan bersedia ganti kartu?")
    await query.edit_message_text(text, reply_markup=acq_keyboard(row.get('bb_id', '')))

async def show_customer_new_message(chat_id, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('current_index', 0)
    if not results or index >= len(results):
        await context.bot.send_message(chat_id=chat_id, text="Tidak ada data pelanggan untuk SITE ID ini.")
        return
    row = results[index]
    text = format_customer_message(row, index, "Apakah Pelanggan bersedia ganti kartu?")
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=acq_keyboard(row.get('bb_id', '')))

# --- Bot Command and Message Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Pilih Branch:",
        reply_markup=branch_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    if state == 'waiting_for_site_id':
        site_id = update.message.text.strip().upper()
        customers = get_customers_by_site_id(site_id)
        if not customers:
            await update.message.reply_text(
                f"SITE ID '{site_id}' tidak ditemukan (atau semua data pelanggan pada SITE ini sudah diproses).\n"
                "Silakan ketik SITE ID yang benar (atau ketik /start untuk kembali):"
            )
            return
        
        context.user_data['state'] = None
        context.user_data['search_results'] = customers
        context.user_data['current_index'] = 0
        await show_customer_for_update(update, context)
    elif state == 'waiting_for_perdana_numbers':
        bb_id = context.user_data.get('pending_bb_id')
        perdana_val = update.message.text.strip()
        
        # Simpan nilai perdana ke Database
        try:
            update_db_perdana(bb_id, perdana_val)
        except Exception as e:
            logger.error(f"Error saving perdana numbers to database: {e}")
            await update.message.reply_text(f"⚠️ Terjadi kesalahan saat menyimpan data: {e}")
            return
            
        confirm_msg = f"Nomor perdana yang diinput: {perdana_val}\nTerima kasih! Pilihan Anda telah disimpan."
        await update.message.reply_text(text=confirm_msg)
        
        # Bersihkan state waiting
        context.user_data['state'] = None
        context.user_data.pop('pending_bb_id', None)
        
        # Lanjut ke data berikutnya
        results = context.user_data.get('search_results', [])
        index = context.user_data.get('current_index', 0)
        next_index = index + 1
        
        if results and next_index < len(results):
            context.user_data['current_index'] = next_index
            await show_customer_new_message(update.message.chat_id, context)
        else:
            await update.message.reply_text("Semua data pelanggan untuk SITE ID ini telah diproses.")
            context.user_data.clear()
    else:
        await update.message.reply_text("Silakan jalankan perintah /start untuk memulai.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:main" or data == "menu:branch":
        context.user_data.clear()
        await query.edit_message_text("Pilih Branch:", reply_markup=branch_keyboard())
    elif data == "menu:cluster":
        branch_name = context.user_data.get('selected_branch')
        if not branch_name:
            await query.edit_message_text("Pilih Branch:", reply_markup=branch_keyboard())
            return
        context.user_data.pop('selected_cluster', None)
        clusters = get_unique_clusters_by_branch(branch_name)
        await query.edit_message_text(
            f"Pilih Cluster di Branch {branch_name}:",
            reply_markup=create_grid_keyboard(clusters, "cluster", back_callback="menu:branch")
        )
    elif data == "menu:site":
        context.user_data['state'] = 'waiting_for_site_id'
        await query.edit_message_text("Silakan ketik SITE ID yang ingin Anda cari (Contoh: SLT077):")
        
    elif data.startswith("branch:"):
        branch_name = data.split(":", 1)[1]
        context.user_data['selected_branch'] = branch_name
        clusters = get_unique_clusters_by_branch(branch_name)
        if not clusters:
            await query.edit_message_text(f"Tidak ada Cluster di branch {branch_name}.", reply_markup=branch_keyboard())
        else:
            await query.edit_message_text(
                f"Pilih Cluster di Branch {branch_name}:",
                reply_markup=create_grid_keyboard(clusters, "cluster", back_callback="menu:branch")
            )
            
    elif data.startswith("cluster:"):
        cluster_name = data.split(":", 1)[1]
        branch_name = context.user_data.get('selected_branch')
        if not branch_name:
            await query.edit_message_text("Pilih Branch:", reply_markup=branch_keyboard())
            return
        
        context.user_data['selected_cluster'] = cluster_name
        sites = get_site_ids_by_branch_and_cluster(branch_name, cluster_name)
        if not sites:
            await query.edit_message_text(
                f"Tidak ada SITE ID di cluster {cluster_name} (Branch {branch_name}).",
                reply_markup=create_grid_keyboard(
                    get_unique_clusters_by_branch(branch_name),
                    "cluster",
                    back_callback="menu:branch"
                )
            )
        else:
            await query.edit_message_text(
                f"Pilih SITE ID di Cluster {cluster_name} (Branch {branch_name}):",
                reply_markup=sites_keyboard(sites, back_callback="menu:cluster")
            )
            
    elif data.startswith("site_id:"):
        site_id = data.split(":", 1)[1]
        customers = get_customers_by_site_id(site_id)
        if not customers:
            branch_name = context.user_data.get('selected_branch')
            cluster_name = context.user_data.get('selected_cluster')
            sites = get_site_ids_by_branch_and_cluster(branch_name, cluster_name) if (branch_name and cluster_name) else []
            keyboard = sites_keyboard(sites, back_callback="menu:cluster") if sites else create_grid_keyboard([], "", back_callback="menu:cluster")
            
            await query.edit_message_text(
                f"Tidak ada data pelanggan yang belum disetujui (Y) untuk SITE ID {site_id}.",
                reply_markup=keyboard
            )
        else:
            context.user_data['state'] = None
            context.user_data['search_results'] = customers
            context.user_data['current_index'] = 0
            await show_customer_for_query(query, context)
            
    elif data.startswith("acq:"):
        _, answer, bb_id = data.split(":", 2)
        
        results = context.user_data.get('search_results', [])
        index = context.user_data.get('current_index', 0)
        
        if results and index < len(results) and results[index].get('bb_id') == bb_id:
            row = results[index]
        else:
            row = None
            
        if answer == 'Y':
            context.user_data['state'] = 'waiting_for_perdana_numbers'
            context.user_data['pending_bb_id'] = bb_id
            prompt = "Silahkan menginput Nomor Perdana Utama :)"
            details_text = format_customer_message(row, index, prompt)
            await query.edit_message_text(text=details_text)
            
        else:  # answer == 'N'
            # Simpan N ke Database
            try:
                update_db_acq(bb_id, 'N')
            except Exception as e:
                logger.error(f"Error saving N to database: {e}")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=f"⚠️ Terjadi kesalahan saat menyimpan data: {e}"
                )
                return
                
            prompt = "Apakah Pelanggan bersedia ganti kartu? Tidak (N)"
            details_text = format_customer_message(row, index, prompt) if row else "Proses selesai. Jawaban: Tidak (N)"
            await query.edit_message_text(text=details_text)
            
            # Lanjut ke data berikutnya
            next_index = index + 1
            if results and next_index < len(results):
                context.user_data['current_index'] = next_index
                await show_customer_new_message(query.message.chat_id, context)
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text="Semua data pelanggan untuk SITE ID ini telah diproses."
                )
                context.user_data.clear()

if __name__ == '__main__':
    # Jalankan inisialisasi database sebelum bot berjalan
    try:
        from db_init import init_db
        print("Mulai inisialisasi database...")
        init_db()
    except Exception as e:
        logger.error(f"Gagal melakukan inisialisasi database: {e}")

    # Membangun aplikasi bot
    app = ApplicationBuilder().token(TOKEN).build()

    # Mendaftarkan handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot sedang berjalan...")
    app.run_polling()
