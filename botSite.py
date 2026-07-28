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

def clean_val(val):
    if not val:
        return val
    return val.strip().strip('"').strip("'").strip()

def get_mysql_config():
    host = 'mysql.railway.internal'
    port = 3306
    user = 'root'
    password = 'botpassword'
    database = 'railway'

    # Try to parse from URL first (common on Railway)
    url = os.environ.get('MYSQL_URL') or os.environ.get('MYSQLURL') or os.environ.get('DATABASE_URL')
    url = clean_val(url)
    if url and url.lower().startswith('mysql://'):
        try:
            url_clean = url[8:]
            if '@' in url_clean:
                auth, rest = url_clean.split('@', 1)
                if ':' in auth:
                    user, password = auth.split(':', 1)
                else:
                    user = auth
                
                if '/' in rest:
                    host_port, database = rest.split('/', 1)
                else:
                    host_port = rest
                    database = 'botsite'
                
                if '?' in database:
                    database = database.split('?', 1)[0]
                
                if ':' in host_port:
                    host, port_str = host_port.split(':', 1)
                    port = int(port_str)
                else:
                    host = host_port
                    port = 3306
                
                host = clean_val(host)
                user = clean_val(user)
                password = clean_val(password)
                database = clean_val(database)
        except Exception as e:
            logger.error(f"Failed to parse connection URL: {e}")

    # Allow overlay with individual environment variables
    env_host = clean_val(os.environ.get('DB_HOST') or os.environ.get('MYSQLHOST') or os.environ.get('MYSQL_HOST'))
    if env_host:
        host = env_host

    port_val = clean_val(os.environ.get('DB_PORT') or os.environ.get('MYSQLPORT') or os.environ.get('MYSQL_PORT'))
    if port_val:
        try:
            port = int(port_val)
        except ValueError:
            pass

    env_user = clean_val(os.environ.get('DB_USER') or os.environ.get('MYSQLUSER') or os.environ.get('MYSQL_USER'))
    if env_user:
        user = env_user

    env_password = clean_val(os.environ.get('DB_PASSWORD') or os.environ.get('MYSQLPASSWORD') or os.environ.get('MYSQL_PASSWORD'))
    if env_password:
        password = env_password

    env_database = clean_val(os.environ.get('DB_DATABASE') or os.environ.get('MYSQLDATABASE') or os.environ.get('MYSQL_DATABASE') or os.environ.get('MYSQL_DB'))
    if env_database:
        database = env_database

    return host, port, user, password, database

# DB Type detection
DB_TYPE = os.environ.get('DB_TYPE')
if not DB_TYPE:
    url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL') or os.environ.get('RAILWAY_SERVICE_MYSQL_URL')
    is_mysql_url = url and url.startswith('mysql://')
    has_mysql_env = (
        os.environ.get('MYSQLHOST') or 
        os.environ.get('MYSQL_HOST') or 
        os.environ.get('RAILWAY_SERVICE_MYSQL_URL') or
        os.environ.get('DB_HOST') not in (None, 'localhost', '127.0.0.1')
    )
    if is_mysql_url or has_mysql_env:
        DB_TYPE = 'mysql'
    else:
        DB_TYPE = 'sqlite'
else:
    DB_TYPE = DB_TYPE.lower()

PLACEHOLDER = '%s' if DB_TYPE == 'mysql' else '?'

def get_db_connection():
    if DB_TYPE == 'mysql':
        host, port, user, password, database = get_mysql_config()
        logger.info(f"Connecting to MySQL with: host={host}, port={port}, user={user}, database={database}")
        
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

def check_bb_id_exists(bb_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE bb_id = {PLACEHOLDER}", (bb_id,))
        row = cursor.fetchone()
        count = row['total'] if isinstance(row, dict) else row[0]
        conn.close()
        return count > 0
    except Exception as e:
        logger.error(f"Error checking bb_id: {e}")
        return False

def add_new_customer(bb_id, site_id, branch, cluster, nama, no_hp, alamat):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO customers (bb_id, Nearest_Site_ID, Branch, Cluster, Nama, No_HP, Alamat) "
            f"VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            (bb_id, site_id, branch, cluster, nama, no_hp, alamat)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error inserting new customer: {e}")
        return False

def get_site_branch_and_cluster(site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT Branch, Cluster FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER} AND Branch IS NOT NULL AND Branch != '' LIMIT 1",
            (site_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['Branch'], row['Cluster']
    except Exception as e:
        logger.error(f"Error getting branch/cluster for site {site_id}: {e}")
    return '', ''

def check_site_stats(site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER}", (site_id,))
        r = cursor.fetchone()
        total = r['total'] if isinstance(r, dict) else r[0]
        
        # Acq = 'Y'
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER} AND UPPER(TRIM(Acq)) = 'Y'", (site_id,))
        r = cursor.fetchone()
        acq_y = r['total'] if isinstance(r, dict) else r[0]
        
        # Acq = 'N'
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER} AND UPPER(TRIM(Acq)) = 'N'", (site_id,))
        r = cursor.fetchone()
        acq_n = r['total'] if isinstance(r, dict) else r[0]
        
        # Unprocessed
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER} AND (Acq IS NULL OR (UPPER(TRIM(Acq)) != 'Y' AND UPPER(TRIM(Acq)) != 'N'))", (site_id,))
        r = cursor.fetchone()
        unprocessed = r['total'] if isinstance(r, dict) else r[0]
        
        # List of first 10 customers
        cursor.execute(f"SELECT bb_id, Nama, No_HP, Acq FROM customers WHERE Nearest_Site_ID = {PLACEHOLDER} LIMIT 10", (site_id,))
        rows = cursor.fetchall()
        customers = []
        for row in rows:
            customers.append(dict(row))
            
        conn.close()
        return {
            'total': total,
            'acq_y': acq_y,
            'acq_n': acq_n,
            'unprocessed': unprocessed,
            'customers': customers
        }
    except Exception as e:
        logger.error(f"Error getting stats for site {site_id}: {e}")
        return {
            'total': 0,
            'acq_y': 0,
            'acq_n': 0,
            'unprocessed': 0,
            'customers': []
        }


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

def site_options_keyboard(site_id):
    keyboard = [
        [InlineKeyboardButton("1. 🔍 Check Site", callback_data=f"site_opt:check:{site_id}")],
        [InlineKeyboardButton("2. ➕ Add Site Data", callback_data=f"site_opt:add:{site_id}")],
        [InlineKeyboardButton("3. 🔄 Conversion Site", callback_data=f"site_opt:conv:{site_id}")],
        [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back")]
    ]
    return InlineKeyboardMarkup(keyboard)

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
    text = update.message.text.strip()
    
    # Global cancel command/word check
    if text.lower() in ('/cancel', 'cancel', 'batal'):
        context.user_data['state'] = None
        site_id = context.user_data.get('selected_site')
        
        # Clear temporary add customer keys
        for key in ['add_bb_id', 'add_nama', 'add_no_hp', 'add_alamat']:
            context.user_data.pop(key, None)
            
        if site_id:
            await update.message.reply_text(
                f"Tindakan dibatalkan.\n\nSITE ID: {site_id}\nSilakan pilih tindakan:",
                reply_markup=site_options_keyboard(site_id)
            )
        else:
            await update.message.reply_text("Tindakan dibatalkan. Silakan ketik /start untuk ke menu utama.")
        return

    if state == 'waiting_for_site_id':
        site_id = text.upper()
        context.user_data['state'] = None
        context.user_data['selected_site'] = site_id
        
        # Auto-fill branch & cluster if not present
        branch, cluster = get_site_branch_and_cluster(site_id)
        if branch:
            context.user_data['selected_branch'] = branch
        if cluster:
            context.user_data['selected_cluster'] = cluster
            
        await update.message.reply_text(
            f"SITE ID: {site_id}\n"
            f"Branch: {branch if branch else '-'}\n"
            f"Cluster: {cluster if cluster else '-'}\n\n"
            "Silakan pilih tindakan yang ingin dilakukan:",
            reply_markup=site_options_keyboard(site_id)
        )
        
    elif state == 'waiting_for_perdana_numbers':
        bb_id = context.user_data.get('pending_bb_id')
        perdana_val = text
        
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
            # Go back to site menu
            site_id = context.user_data.get('selected_site')
            if site_id:
                await update.message.reply_text(
                    f"Kembali ke menu tindakan untuk SITE ID {site_id}:",
                    reply_markup=site_options_keyboard(site_id)
                )
            else:
                context.user_data.clear()

    elif state == 'waiting_for_add_bb_id':
        bb_id = text
        if check_bb_id_exists(bb_id):
            await update.message.reply_text(
                f"Nomor IH (bb_id) '{bb_id}' sudah terdaftar. Silakan masukkan Nomor IH yang lain (atau ketik 'batal'):"
            )
            return
        
        context.user_data['add_bb_id'] = bb_id
        context.user_data['state'] = 'waiting_for_add_nama'
        await update.message.reply_text(
            f"Nomor IH diterima: {bb_id}\n\n"
            f"Silakan masukkan **Nama Pelanggan**:"
        )

    elif state == 'waiting_for_add_nama':
        nama = text
        context.user_data['add_nama'] = nama
        context.user_data['state'] = 'waiting_for_add_no_hp'
        await update.message.reply_text(
            f"Nama diterima: {nama}\n\n"
            f"Silakan masukkan **Nomor HP Pelanggan**:"
        )

    elif state == 'waiting_for_add_no_hp':
        no_hp = text
        context.user_data['add_no_hp'] = no_hp
        context.user_data['state'] = 'waiting_for_add_alamat'
        await update.message.reply_text(
            f"Nomor HP diterima: {no_hp}\n\n"
            f"Silakan masukkan **Alamat Pelanggan**:"
        )

    elif state == 'waiting_for_add_alamat':
        alamat = text
        bb_id = context.user_data.get('add_bb_id')
        site_id = context.user_data.get('selected_site')
        branch = context.user_data.get('selected_branch', '')
        cluster = context.user_data.get('selected_cluster', '')
        nama = context.user_data.get('add_nama', '')
        no_hp = context.user_data.get('add_no_hp', '')
        
        success = add_new_customer(
            bb_id=bb_id,
            site_id=site_id,
            branch=branch,
            cluster=cluster,
            nama=nama,
            no_hp=no_hp,
            alamat=alamat
        )
        
        # Clear temporary keys and states
        context.user_data['state'] = None
        for key in ['add_bb_id', 'add_nama', 'add_no_hp', 'add_alamat']:
            context.user_data.pop(key, None)
            
        if success:
            await update.message.reply_text(
                f"✅ Data pelanggan baru berhasil ditambahkan!\n\n"
                f"• SITE ID: {site_id}\n"
                f"• IH (bb_id): {bb_id}\n"
                f"• Nama: {nama}\n"
                f"• No HP: {no_hp}\n"
                f"• Alamat: {alamat}"
            )
        else:
            await update.message.reply_text("⚠️ Terjadi kesalahan saat menyimpan data baru ke database.")
            
        # Go back to site menu
        if site_id:
            await update.message.reply_text(
                f"SITE ID: {site_id}\n"
                f"Silakan pilih tindakan berikutnya:",
                reply_markup=site_options_keyboard(site_id)
            )
            
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
        context.user_data['selected_site'] = site_id
        
        # Auto-fill branch & cluster if not present
        if not context.user_data.get('selected_branch') or not context.user_data.get('selected_cluster'):
            branch, cluster = get_site_branch_and_cluster(site_id)
            if branch:
                context.user_data['selected_branch'] = branch
            if cluster:
                context.user_data['selected_cluster'] = cluster
                
        await query.edit_message_text(
            f"SITE ID: {site_id}\n"
            f"Branch: {context.user_data.get('selected_branch', '-')}\n"
            f"Cluster: {context.user_data.get('selected_cluster', '-')}\n\n"
            "Silakan pilih tindakan yang ingin dilakukan:",
            reply_markup=site_options_keyboard(site_id)
        )
        
    elif data.startswith("site_opt:check:"):
        site_id = data.split(":", 2)[2]
        stats = check_site_stats(site_id)
        
        text = (
            f"📊 *STATISTIK SITE ID: {site_id}*\n"
            f"• Total Pelanggan: {stats['total']}\n"
            f"• Bersedia (Y): {stats['acq_y']}\n"
            f"• Tidak Bersedia (N): {stats['acq_n']}\n"
            f"• Belum Diproses: {stats['unprocessed']}\n\n"
            f"📋 *Daftar Pelanggan (Maks 10):*\n"
        )
        
        if stats['customers']:
            for i, cust in enumerate(stats['customers']):
                status_acq = cust.get('Acq') or 'Belum Diproses'
                text += f"{i+1}. IH: {cust.get('bb_id')} | Nama: {cust.get('Nama')} (Status: {status_acq})\n"
        else:
            text += "Tidak ada data pelanggan.\n"
            
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

    elif data.startswith("site_opt:add:"):
        site_id = data.split(":", 2)[2]
        context.user_data['selected_site'] = site_id
        context.user_data['state'] = 'waiting_for_add_bb_id'
        
        if not context.user_data.get('selected_branch') or not context.user_data.get('selected_cluster'):
            branch, cluster = get_site_branch_and_cluster(site_id)
            if branch:
                context.user_data['selected_branch'] = branch
            if cluster:
                context.user_data['selected_cluster'] = cluster
                
        await query.edit_message_text(
            f"➕ *Tambah Data Pelanggan Baru*\n"
            f"Site ID: {site_id}\n\n"
            f"Silakan masukkan **Nomor IH (bb_id)**:\n"
            f"(Ketik 'batal' untuk membatalkan)",
            parse_mode="Markdown"
        )

    elif data.startswith("site_opt:conv:"):
        site_id = data.split(":", 2)[2]
        customers = get_customers_by_site_id(site_id)
        if not customers:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")]
            ])
            await query.edit_message_text(
                f"Tidak ada data pelanggan yang belum disetujui (Y) untuk SITE ID {site_id}.",
                reply_markup=keyboard
            )
        else:
            context.user_data['state'] = None
            context.user_data['search_results'] = customers
            context.user_data['current_index'] = 0
            await show_customer_for_query(query, context)

    elif data.startswith("site_opt:back_to_menu:"):
        site_id = data.split(":", 2)[2]
        await query.edit_message_text(
            f"SITE ID: {site_id}\n"
            f"Branch: {context.user_data.get('selected_branch', '-')}\n"
            f"Cluster: {context.user_data.get('selected_cluster', '-')}\n\n"
            "Silakan pilih tindakan yang ingin dilakukan:",
            reply_markup=site_options_keyboard(site_id)
        )

    elif data == "site_opt:back":
        branch_name = context.user_data.get('selected_branch')
        cluster_name = context.user_data.get('selected_cluster')
        if branch_name and cluster_name:
            sites = get_site_ids_by_branch_and_cluster(branch_name, cluster_name)
            await query.edit_message_text(
                f"Pilih SITE ID di Cluster {cluster_name} (Branch {branch_name}):",
                reply_markup=sites_keyboard(sites, back_callback="menu:cluster")
            )
        else:
            context.user_data.clear()
            context.user_data['state'] = 'waiting_for_site_id'
            await query.edit_message_text("Silakan ketik SITE ID yang ingin Anda cari (Contoh: SLT077):")
            
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
