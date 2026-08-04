import os
import math
import sqlite3
import pymysql
import logging
# pyrefly: ignore [missing-import]
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
from db import get_db_connection as _get_db_conn_raw, DB_TYPE, PLACEHOLDER

def get_db_connection():
    return _get_db_conn_raw(as_dict=True)


def get_unique_column_values(column_name):
    db_col = column_name.lower()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT {db_col} FROM site_focus WHERE {db_col} IS NOT NULL AND {db_col} != '' ORDER BY {db_col}")
        values = [row[db_col] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        conn.close()
        return values
    except Exception as e:
        logger.error(f"Error reading {column_name} from site_focus: {e}")
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
            f"SELECT DISTINCT cluster FROM site_focus WHERE branch = {PLACEHOLDER} AND cluster IS NOT NULL AND cluster != '' ORDER BY cluster",
            (branch_name,)
        )
        values = [row['cluster'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        conn.close()
        return values
    except Exception as e:
        logger.error(f"Error reading clusters for branch {branch_name} from site_focus: {e}")
        return []

def get_site_ids_by_branch_and_cluster(branch_name, cluster_name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT site_id FROM site_focus WHERE branch = {PLACEHOLDER} AND cluster = {PLACEHOLDER} AND site_id IS NOT NULL AND site_id != '' ORDER BY site_id",
            (branch_name, cluster_name)
        )
        site_ids = [row['site_id'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        conn.close()
        return site_ids
    except Exception as e:
        logger.error(f"Error reading sites by branch {branch_name} and cluster {cluster_name} from site_focus: {e}")
        return []

def get_site_ids_by_filter(filter_col, filter_val):
    db_col = filter_col.lower()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT site_id FROM site_focus WHERE {db_col} = {PLACEHOLDER} AND site_id IS NOT NULL AND site_id != '' ORDER BY site_id",
            (filter_val,)
        )
        site_ids = [row['site_id'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        conn.close()
        return site_ids
    except Exception as e:
        logger.error(f"Error reading sites by {filter_col} from site_focus: {e}")
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
        # Ambil data pelanggan IndiHome Non-Telkomsel yang status Acq-nya 'N' (belum dikonversi)
        cursor.execute(
            f"SELECT * FROM customers WHERE UPPER(TRIM(site_id)) = {PLACEHOLDER} AND (acq IS NULL OR UPPER(TRIM(acq)) = 'N')",
            (site_id.strip().upper(),)
        )
        customers = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        logger.error(f"Error reading customers by site: {e}")
    return customers


def update_db_acq(bb_id, acq_val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE customers SET acq = {PLACEHOLDER} WHERE bb_id = {PLACEHOLDER}", (acq_val, bb_id))
    conn.commit()
    conn.close()

def update_db_perdana(bb_id, perdana_val):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE customers SET acq = 'Y', nomor_baru = {PLACEHOLDER} WHERE bb_id = {PLACEHOLDER}", (perdana_val, bb_id))
    conn.commit()
    conn.close()

def get_site_branch_and_cluster(site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT branch, cluster FROM site_focus WHERE site_id = {PLACEHOLDER} AND branch IS NOT NULL AND branch != '' LIMIT 1",
            (site_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            br = row['branch'] if isinstance(row, dict) else row[0]
            cl = row['cluster'] if isinstance(row, dict) else row[1]
            return br, cl
    except Exception as e:
        logger.error(f"Error getting branch/cluster for site {site_id} from site_focus: {e}")
    return '', ''

def check_site_stats(site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE site_id = {PLACEHOLDER}", (site_id,))
        r = cursor.fetchone()
        total = r['total'] if isinstance(r, dict) else r[0]
        
        # Acq = 'Y'
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE site_id = {PLACEHOLDER} AND UPPER(TRIM(acq)) = 'Y'", (site_id,))
        r = cursor.fetchone()
        acq_y = r['total'] if isinstance(r, dict) else r[0]
        
        # Acq = 'N'
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE site_id = {PLACEHOLDER} AND UPPER(TRIM(acq)) = 'N'", (site_id,))
        r = cursor.fetchone()
        acq_n = r['total'] if isinstance(r, dict) else r[0]
        
        # Unprocessed
        cursor.execute(f"SELECT COUNT(*) as total FROM customers WHERE site_id = {PLACEHOLDER} AND (acq IS NULL OR (UPPER(TRIM(acq)) != 'Y' AND UPPER(TRIM(acq)) != 'N'))", (site_id,))
        r = cursor.fetchone()
        unprocessed = r['total'] if isinstance(r, dict) else r[0]
        
        # List of first 10 customers
        cursor.execute(f"SELECT bb_id, nama, no_hp, acq FROM customers WHERE site_id = {PLACEHOLDER} LIMIT 10", (site_id,))
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


def get_potensi_branch_and_cluster(site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT branch, cluster FROM potensi_site WHERE site_id = {PLACEHOLDER} AND branch IS NOT NULL AND branch != '' LIMIT 1",
            (site_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['branch'], row['cluster']
    except Exception as e:
        logger.error(f"Error getting branch/cluster for site {site_id} in potensi_site: {e}")
    return '', ''

def get_potensi_categories(branch, cluster, site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT DISTINCT kategori FROM potensi_site "
            f"WHERE branch = {PLACEHOLDER} AND cluster = {PLACEHOLDER} AND site_id = {PLACEHOLDER} "
            f"AND kategori IS NOT NULL AND kategori != '' ORDER BY kategori",
            (branch, cluster, site_id)
        )
        categories = [row['kategori'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        conn.close()
        return categories
    except Exception as e:
        logger.error(f"Error getting potensi categories: {e}")
        return []

def get_potensi_categories_with_counts(branch, cluster, site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT kategori, COUNT(*) as total FROM potensi_site "
            f"WHERE branch = {PLACEHOLDER} AND cluster = {PLACEHOLDER} AND site_id = {PLACEHOLDER} "
            f"AND kategori IS NOT NULL AND kategori != '' "
            f"GROUP BY kategori "
            f"ORDER BY kategori",
            (branch, cluster, site_id)
        )
        results = []
        for row in cursor.fetchall():
            kategori = row['kategori'] if isinstance(row, dict) else row[0]
            total = row['total'] if isinstance(row, dict) else row[1]
            results.append({
                'kategori': kategori,
                'total': total
            })
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error getting potensi categories with counts: {e}")
        return []

def get_potensi_by_category(branch, cluster, site_id, category):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM potensi_site "
            f"WHERE branch = {PLACEHOLDER} AND cluster = {PLACEHOLDER} AND site_id = {PLACEHOLDER} AND kategori = {PLACEHOLDER} "
            f"ORDER BY distance ASC",
            (branch, cluster, site_id, category)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error getting potensi by category: {e}")
        return []

def get_site_metadata(site_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT branch, cluster, kabupaten FROM potensi_site "
            f"WHERE site_id = {PLACEHOLDER} AND branch IS NOT NULL AND branch != '' LIMIT 1",
            (site_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row['branch'], row['cluster'], row['kabupaten']
    except Exception as e:
        logger.error(f"Error getting metadata for site {site_id} from potensi_site: {e}")
    return '', '', ''

def get_next_potensi_no():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(no) as max_no FROM potensi_site")
        row = cursor.fetchone()
        conn.close()
        max_no = row['max_no'] if isinstance(row, dict) else row[0]
        if max_no is None:
            return 1
        return int(max_no) + 1
    except Exception as e:
        logger.error(f"Error getting next potensi no: {e}")
        return 1

def get_all_distinct_categories():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT kategori FROM potensi_site WHERE kategori IS NOT NULL AND kategori != '' ORDER BY kategori")
        categories = [row['kategori'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        conn.close()
        return categories
    except Exception as e:
        logger.error(f"Error getting distinct categories: {e}")
        return []

def add_new_potensi(site_id, nama, kategori, branch, cluster, kabupaten, longitude, latitude, distance_km):
    try:
        no = get_next_potensi_no()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"INSERT INTO potensi_site (no, site_id, nama, kategori, kabupaten, branch, cluster, long, lat, distance) "
            f"VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            (no, site_id, nama, kategori, kabupaten, branch, cluster, longitude, latitude, distance_km)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error inserting new potensi: {e}")
        return False

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    try:
        # Radius of the earth in km
        R = 6371.0
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return round(distance, 2)
    except Exception as e:
        logger.error(f"Error calculating haversine distance: {e}")
        return 0.0

def get_site_focus_coords(site_id):
    if not site_id:
        return None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT lat, long FROM site_focus WHERE UPPER(site_id) = {PLACEHOLDER} LIMIT 1",
            (site_id.strip().upper(),)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            lat = row['lat'] if isinstance(row, dict) else row[0]
            lon = row['long'] if isinstance(row, dict) else row[1]
            if lat is not None and lon is not None:
                lat_f, lon_f = float(lat), float(lon)
                if lat_f != 0.0 or lon_f != 0.0:
                    return lat_f, lon_f
    except Exception as e:
        logger.error(f"Error getting coordinates for site {site_id} from site_focus: {e}")
    return None

def get_site_coordinates(site_id):
    if not site_id:
        return None
    # Try site_focus table first
    coords = get_site_focus_coords(site_id)
    if coords:
        return coords
        
    # Fallback to potensi_site table if not found in site_focus
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT lat, long FROM potensi_site "
            f"WHERE UPPER(site_id) = {PLACEHOLDER} AND lat IS NOT NULL AND lat != 0.0 LIMIT 1",
            (site_id.strip().upper(),)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            lat = row['lat'] if isinstance(row, dict) else row[0]
            lon = row['long'] if isinstance(row, dict) else row[1]
            if lat is not None and lon is not None:
                lat_f, lon_f = float(lat), float(lon)
                if lat_f != 0.0 or lon_f != 0.0:
                    return lat_f, lon_f
    except Exception as e:
        logger.error(f"Error getting coordinates for site {site_id} from potensi_site fallback: {e}")
        
    return None



def make_gmaps_url(lat, lon):
    if lat is not None and lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
            if lat_f != 0.0 or lon_f != 0.0:
                return f"https://www.google.com/maps?q={lat_f},{lon_f}"
        except (ValueError, TypeError):
            pass
    return None

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

def site_options_keyboard(site_id, lat=None, lon=None):
    keyboard = []
    maps_url = make_gmaps_url(lat, lon)
    if maps_url:
        keyboard.append([InlineKeyboardButton("📍 Buka Lokasi Site di Google Maps", url=maps_url)])
    keyboard.extend([
        [InlineKeyboardButton("1. 🔍 Check Potensi Surrounding", callback_data=f"site_opt:potensi:{site_id}")],
        [InlineKeyboardButton("2. ➕ Add New Potensi Surrounding", callback_data=f"site_opt:add:{site_id}")],
        [InlineKeyboardButton("3. 🔄 Kunjungan Ke Pelanggan Indihome Non Tsel", callback_data=f"site_opt:conv:{site_id}")],
        [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back")]
    ])
    return InlineKeyboardMarkup(keyboard)

def acq_keyboard(bb_id, lat=None, lon=None):
    keyboard = []
    maps_url = make_gmaps_url(lat, lon)
    if maps_url:
        keyboard.append([InlineKeyboardButton("📍 Buka Lokasi Pelanggan di Google Maps", url=maps_url)])
    keyboard.append([
        InlineKeyboardButton("Ya (Y)", callback_data=f"acq:Y:{bb_id}"),
        InlineKeyboardButton("Tidak (N)", callback_data=f"acq:N:{bb_id}")
    ])
    return InlineKeyboardMarkup(keyboard)

# --- Customer Display Helpers ---

def get_dict_val(d, *keys):
    if not isinstance(d, dict):
        return ''
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
        k_lower = k.lower()
        if k_lower in d and d[k_lower] is not None:
            return d[k_lower]
    return ''

def format_customer_message(row, index, prompt):
    if not row:
        return prompt
    lat = get_dict_val(row, 'lat', 'Latitude')
    lon = get_dict_val(row, 'long', 'Longitude')
    maps_url = make_gmaps_url(lat, lon)
    maps_str = f"[📍 Buka Peta Google Maps]({maps_url})" if maps_url else "-"
    return (
        f"No: {index + 1}\n"
        f"SITE_ID: {get_dict_val(row, 'site_id', 'Nearest_Site_ID')}\n"
        f"Nomor IH: {get_dict_val(row, 'bb_id')}\n"
        f"Nomor HP: {get_dict_val(row, 'no_hp', 'No_HP')}\n"
        f"Nama Pelanggan: {get_dict_val(row, 'nama', 'Nama')}\n"
        f"Branch: {get_dict_val(row, 'branch', 'Branch')}\n"
        f"Cluster: {get_dict_val(row, 'cluster', 'Cluster')}\n"
        f"Alamat: {get_dict_val(row, 'alamat', 'Alamat')}\n"
        f"Kodepos: {get_dict_val(row, 'kodepos', 'Kodepos')}\n"
        f"Peta Lokasi: {maps_str}\n\n"
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
    lat = get_dict_val(row, 'lat', 'Latitude')
    lon = get_dict_val(row, 'long', 'Longitude')
    await update.message.reply_text(text, reply_markup=acq_keyboard(get_dict_val(row, 'bb_id'), lat, lon), parse_mode="Markdown")

async def show_customer_for_query(query, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('current_index', 0)
    if not results or index >= len(results):
        await query.edit_message_text("Tidak ada data pelanggan untuk SITE ID ini.")
        return
    row = results[index]
    text = format_customer_message(row, index, "Apakah Pelanggan bersedia ganti kartu?")
    lat = get_dict_val(row, 'lat', 'Latitude')
    lon = get_dict_val(row, 'long', 'Longitude')
    await query.edit_message_text(text, reply_markup=acq_keyboard(get_dict_val(row, 'bb_id'), lat, lon), parse_mode="Markdown")

async def show_customer_new_message(chat_id, context: ContextTypes.DEFAULT_TYPE):
    results = context.user_data.get('search_results', [])
    index = context.user_data.get('current_index', 0)
    if not results or index >= len(results):
        await context.bot.send_message(chat_id=chat_id, text="Tidak ada data pelanggan untuk SITE ID ini.")
        return
    row = results[index]
    text = format_customer_message(row, index, "Apakah Pelanggan bersedia ganti kartu?")
    lat = get_dict_val(row, 'lat', 'Latitude')
    lon = get_dict_val(row, 'long', 'Longitude')
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=acq_keyboard(get_dict_val(row, 'bb_id'), lat, lon), parse_mode="Markdown")


# --- Bot Command and Message Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Pilih Branch:",
        reply_markup=branch_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text.strip() if update.message.text else ""
    
    # Global cancel command/word check
    if text.lower() in ('/cancel', 'cancel', 'batal'):
        context.user_data['state'] = None
        site_id = context.user_data.get('selected_site')
        
        # Clear temporary keys
        for key in ['add_bb_id', 'add_nama', 'add_no_hp', 'add_alamat', 'add_potensi_kategori', 'add_potensi_nama', 'add_potensi_long', 'add_potensi_lat', 'add_potensi_distance', 'all_categories']:
            context.user_data.pop(key, None)
            
        if site_id:
            await update.message.reply_text("Tindakan dibatalkan.", reply_markup=ReplyKeyboardRemove())
            await update.message.reply_text(
                f"SITE ID: {site_id}\nSilakan pilih tindakan:",
                reply_markup=site_options_keyboard(site_id)
            )
        else:
            await update.message.reply_text("Tindakan dibatalkan. Silakan ketik /start untuk ke menu utama.", reply_markup=ReplyKeyboardRemove())
        return

    if state == 'waiting_for_site_id':
        site_id = text.upper()
        context.user_data['state'] = None
        context.user_data['selected_site'] = site_id
        
        # Auto-fill branch & cluster if not present
        branch, cluster = get_site_branch_and_cluster(site_id)
        if not branch:
            branch, cluster = get_potensi_branch_and_cluster(site_id)
        if branch:
            context.user_data['selected_branch'] = branch
        if cluster:
            context.user_data['selected_cluster'] = cluster
            
        coords = get_site_coordinates(site_id)
        site_lat, site_lon = coords if coords else (None, None)
        maps_url = make_gmaps_url(site_lat, site_lon)
        maps_str = f"[📍 {site_lat},{site_lon} (Buka Google Maps)]({maps_url})" if maps_url else "-"
            
        await update.message.reply_text(
            f"SITE ID: {site_id}\n"
            f"Branch: {branch if branch else '-'}\n"
            f"Cluster: {cluster if cluster else '-'}\n"
            f"Koordinat: {maps_str}\n\n"
            "Silakan pilih tindakan yang ingin dilakukan:",
            reply_markup=site_options_keyboard(site_id, site_lat, site_lon),
            parse_mode="Markdown"
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

    elif state == 'waiting_for_add_potensi_kategori':
        category = text
        context.user_data['add_potensi_kategori'] = category
        context.user_data['state'] = 'waiting_for_add_potensi_nama'
        site_id = context.user_data.get('selected_site')
        
        await update.message.reply_text(
            f"Kategori diterima: *{category}*\n\n"
            f"Silakan masukkan **Nama Lokasi**:\n"
            f"(Ketik 'batal' untuk membatalkan)",
            parse_mode="Markdown"
        )

    elif state == 'waiting_for_add_potensi_nama':
        nama = text
        context.user_data['add_potensi_nama'] = nama
        context.user_data['state'] = 'waiting_for_add_potensi_koordinat'
        
        site_id = context.user_data.get('selected_site')
        coords = get_site_coordinates(site_id)
        site_gmaps = make_gmaps_url(coords[0], coords[1]) if coords else None
        site_maps_info = f"\n💡 *Acuan Peta Site {site_id}:* [📍 Buka Google Maps Site]({site_gmaps})\n" if site_gmaps else ""
        
        keyboard = [
            [KeyboardButton("📍 Kirim Lokasi / Pilih dari Peta", request_location=True)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Nama Lokasi diterima: *{nama}*\n"
            f"SITE ID: *{site_id}*\n"
            f"{site_maps_info}\n"
            f"📍 *Cara Menentukan Lokasi Potensi di Peta:*\n\n"
            f"1️⃣ **Pilih Titik di Peta (Rekomendasi)**:\n"
            f"   Tekan tombol **📍 Kirim Lokasi / Pilih dari Peta** di bawah. Saat peta muncul, **geser pin/jarum peta** ke lokasi potensi yang Anda inginkan (tidak harus lokasi Anda saat ini), lalu tekan *Kirim Lokasi Ini*.\n\n"
            f"2️⃣ **Ketik Koordinat Desimal dari Google Maps**:\n"
            f"   Buka Google Maps, tahan/klik titik lokasi potensi untuk menyalin koordinat, lalu ketik di sini dalam format `latitude,longitude`\n"
            f"   *(Contoh: `-3.023201,108.093191`)*\n\n"
            f"(Ketik 'batal' untuk membatalkan)",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif state == 'waiting_for_add_potensi_koordinat':
        if update.message.location:
            latitude = update.message.location.latitude
            longitude = update.message.location.longitude
        elif text:
            try:
                parts = [p.strip() for p in text.split(',')]
                if len(parts) != 2:
                    raise ValueError("Must contain exactly one comma separating lat and long")
                latitude = float(parts[0])
                longitude = float(parts[1])
            except (ValueError, IndexError):
                await update.message.reply_text(
                    "⚠️ Format koordinat tidak valid.\n\n"
                    "Silakan tekan tombol **📍 Kirim Lokasi / Pilih dari Peta** lalu **geser pin lokasi pada peta** ke titik yang Anda pilih, "
                    "atau ketik manual format desimal `latitude,longitude` (contoh: `-3.023201,108.093191`):",
                    parse_mode="Markdown"
                )
                return
        else:
            await update.message.reply_text(
                "⚠️ Mohon kirim lokasi via peta atau masukkan koordinat `latitude,longitude`:",
                parse_mode="Markdown"
            )
            return


        context.user_data['add_potensi_lat'] = latitude
        context.user_data['add_potensi_long'] = longitude
        
        # Look up parent site coordinates to auto-calculate distance
        site_id = context.user_data.get('selected_site')
        site_coords = get_site_coordinates(site_id)
        
        if site_coords:
            site_lat, site_lon = site_coords
            distance_km = calculate_haversine_distance(latitude, longitude, site_lat, site_lon)
            
            # Save directly to database
            branch = context.user_data.get('selected_branch', '')
            cluster = context.user_data.get('selected_cluster', '')
            kabupaten = context.user_data.get('selected_kabupaten', '')
            kategori = context.user_data.get('add_potensi_kategori', '')
            nama = context.user_data.get('add_potensi_nama', '')
            
            success = add_new_potensi(
                site_id=site_id,
                nama=nama,
                kategori=kategori,
                branch=branch,
                cluster=cluster,
                kabupaten=kabupaten,
                longitude=longitude,
                latitude=latitude,
                distance_km=distance_km
            )
            
            # Clear state and temporary keys
            context.user_data['state'] = None
            for key in ['add_potensi_kategori', 'add_potensi_nama', 'add_potensi_long', 'add_potensi_lat', 'add_potensi_distance', 'all_categories']:
                context.user_data.pop(key, None)
                
            if success:
                await update.message.reply_text(
                    f"✅ Data potensi site baru berhasil ditambahkan!\n\n"
                    f"• SITE ID: {site_id}\n"
                    f"• Kategori: {kategori}\n"
                    f"• Nama Lokasi: {nama}\n"
                    f"• Longitude: {longitude}\n"
                    f"• Latitude: {latitude}\n"
                    f"• Jarak (Dihitung Otomatis): *{distance_km} Km* dari koordinat site (`{site_lat},{site_lon}`)",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text("⚠️ Terjadi kesalahan saat menyimpan data potensi baru ke database.", reply_markup=ReplyKeyboardRemove())
                
            # Go back to site menu
            if site_id:
                await update.message.reply_text(
                    f"SITE ID: {site_id}\n"
                    f"Silakan pilih tindakan berikutnya:",
                    reply_markup=site_options_keyboard(site_id)
                )
        else:
            # Fallback if parent site coordinates cannot be found
            context.user_data['state'] = 'waiting_for_add_potensi_distance'
            await update.message.reply_text(
                f"Koordinat lokasi baru diterima:\n"
                f"• Latitude: `{latitude}`\n"
                f"• Longitude: `{longitude}`\n\n"
                f"⚠️ Koordinat Site {site_id} tidak ditemukan di database. Silakan masukkan nilai **Jarak (Km)** secara manual (contoh: 1.33):\n"
                f"(Ketik 'batal' untuk membatalkan)",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown"
            )

    elif state == 'waiting_for_add_potensi_distance':
        try:
            distance_km = float(text)
        except ValueError:
            await update.message.reply_text(
                "⚠️ Format Jarak salah. Silakan masukkan angka desimal yang valid (contoh: 1.33):"
            )
            return
            
        site_id = context.user_data.get('selected_site')
        branch = context.user_data.get('selected_branch', '')
        cluster = context.user_data.get('selected_cluster', '')
        kabupaten = context.user_data.get('selected_kabupaten', '')
        kategori = context.user_data.get('add_potensi_kategori', '')
        nama = context.user_data.get('add_potensi_nama', '')
        longitude = context.user_data.get('add_potensi_long')
        latitude = context.user_data.get('add_potensi_lat')
        
        success = add_new_potensi(
            site_id=site_id,
            nama=nama,
            kategori=kategori,
            branch=branch,
            cluster=cluster,
            kabupaten=kabupaten,
            longitude=longitude,
            latitude=latitude,
            distance_km=distance_km
        )
        
        # Clear temporary keys and state
        context.user_data['state'] = None
        for key in ['add_potensi_kategori', 'add_potensi_nama', 'add_potensi_long', 'add_potensi_lat', 'add_potensi_distance', 'all_categories']:
            context.user_data.pop(key, None)
            
        if success:
            await update.message.reply_text(
                f"✅ Data potensi site baru berhasil ditambahkan!\n\n"
                f"• SITE ID: {site_id}\n"
                f"• Kategori: {kategori}\n"
                f"• Nama Lokasi: {nama}\n"
                f"• Longitude: {longitude}\n"
                f"• Latitude: {latitude}\n"
                f"• Jarak: {distance_km} Km"
            )
        else:
            await update.message.reply_text("⚠️ Terjadi kesalahan saat menyimpan data potensi baru ke database.")
            
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
            if not branch:
                branch, cluster = get_potensi_branch_and_cluster(site_id)
            if branch:
                context.user_data['selected_branch'] = branch
            if cluster:
                context.user_data['selected_cluster'] = cluster
                
        coords = get_site_coordinates(site_id)
        site_lat, site_lon = coords if coords else (None, None)
        maps_url = make_gmaps_url(site_lat, site_lon)
        maps_str = f"[📍 {site_lat},{site_lon} (Buka Google Maps)]({maps_url})" if maps_url else "-"
                
        await query.edit_message_text(
            f"SITE ID: {site_id}\n"
            f"Branch: {context.user_data.get('selected_branch', '-')}\n"
            f"Cluster: {context.user_data.get('selected_cluster', '-')}\n"
            f"Koordinat: {maps_str}\n\n"
            "Silakan pilih tindakan yang ingin dilakukan:",
            reply_markup=site_options_keyboard(site_id, site_lat, site_lon),
            parse_mode="Markdown"
        )
        
    elif data.startswith("site_opt:potensi:"):
        site_id = data.split(":", 2)[2]
        
        # Resolve branch & cluster
        branch = context.user_data.get('selected_branch', '')
        cluster = context.user_data.get('selected_cluster', '')
        if not branch or not cluster:
            branch, cluster = get_site_branch_and_cluster(site_id)
            if not branch:
                branch, cluster = get_potensi_branch_and_cluster(site_id)
            if branch:
                context.user_data['selected_branch'] = branch
            if cluster:
                context.user_data['selected_cluster'] = cluster
                
        categories = get_potensi_categories_with_counts(branch, cluster, site_id)
        if not categories:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")]
            ])
            await query.edit_message_text(
                f"Tidak ada data potensi site untuk:\n"
                f"Branch: {branch if branch else '-'}\n"
                f"Cluster: {cluster if cluster else '-'}\n"
                f"Site ID: {site_id}",
                reply_markup=keyboard
            )
            return
            
        context.user_data['potensi_categories'] = categories
        
        keyboard = []
        for i, item in enumerate(categories):
            cat_name = item['kategori']
            count = item['total']
            button_text = f"{cat_name} ({count})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"pot_cat:{site_id}:{i}")])
        keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")])
        
        await query.edit_message_text(
            f"🔍 *CHECK POTENSI SITE: {site_id}*\n"
            f"Branch: {branch if branch else '-'}\n"
            f"Cluster: {cluster if cluster else '-'}\n\n"
            f"Silakan pilih Kategori Potensi:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("pot_cat:"):
        _, site_id, idx_str = data.split(":", 2)
        idx = int(idx_str)
        
        categories = context.user_data.get('potensi_categories', [])
        if not categories or idx >= len(categories):
            branch = context.user_data.get('selected_branch', '')
            cluster = context.user_data.get('selected_cluster', '')
            categories = get_potensi_categories_with_counts(branch, cluster, site_id)
            context.user_data['potensi_categories'] = categories
            
        if not categories or idx >= len(categories):
            await query.edit_message_text(
                "Terjadi kesalahan: Kategori tidak ditemukan.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")]
                ])
            )
            return
            
        category = categories[idx]['kategori']
        branch = context.user_data.get('selected_branch', '')
        cluster = context.user_data.get('selected_cluster', '')
        
        potensi_list = get_potensi_by_category(branch, cluster, site_id, category)
        
        text = (
            f"📋 *POTENSI SITE: {site_id}*\n"
            f"Kategori: *{category}*\n"
            f"Branch: {branch if branch else '-'}\n"
            f"Cluster: {cluster if cluster else '-'}\n\n"
            f"*Daftar Lokasi Potensi:*\n"
        )
        
        if potensi_list:
            for i, p in enumerate(potensi_list):
                dist = get_dict_val(p, 'distance', 'distance_km')
                dist_str = f"{dist} Km" if dist != '' and dist is not None else "-"
                plat = get_dict_val(p, 'lat', 'latitude')
                plon = get_dict_val(p, 'long', 'longitude')
                purl = make_gmaps_url(plat, plon)
                if purl:
                    coord_str = f"[📍 {plat},{plon} (Buka Google Maps)]({purl})"
                else:
                    coord_str = f"`{plat},{plon}`" if (plat or plon) else "-"
                text += (
                    f"{i+1}. *{get_dict_val(p, 'nama')}*\n"
                    f"   • Jarak: {dist_str}\n"
                    f"   • Koordinat: {coord_str}\n"
                )
        else:
            text += "Tidak ada data lokasi potensi untuk kategori ini.\n"
            
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Kembali ke Kategori", callback_data=f"pot_back_to_cats:{site_id}")],
            [InlineKeyboardButton("🏠 Menu Utama", callback_data=f"site_opt:back_to_menu:{site_id}")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

    elif data.startswith("pot_back_to_cats:"):
        site_id = data.split(":", 1)[1]
        branch = context.user_data.get('selected_branch', '')
        cluster = context.user_data.get('selected_cluster', '')
        categories = context.user_data.get('potensi_categories', [])
        
        if not categories:
            categories = get_potensi_categories_with_counts(branch, cluster, site_id)
            context.user_data['potensi_categories'] = categories
            
        keyboard = []
        for i, item in enumerate(categories):
            cat_name = item['kategori']
            count = item['total']
            button_text = f"{cat_name} ({count})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"pot_cat:{site_id}:{i}")])
        keyboard.append([InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")])
        
        await query.edit_message_text(
            f"🔍 *CHECK POTENSI SITE: {site_id}*\n"
            f"Branch: {branch if branch else '-'}\n"
            f"Cluster: {cluster if cluster else '-'}\n\n"
            f"Silakan pilih Kategori Potensi:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("site_opt:add:"):
        site_id = data.split(":", 2)[2]
        context.user_data['selected_site'] = site_id
        
        branch, cluster, kabupaten = get_site_metadata(site_id)
        if branch:
            context.user_data['selected_branch'] = branch
        if cluster:
            context.user_data['selected_cluster'] = cluster
        if kabupaten:
            context.user_data['selected_kabupaten'] = kabupaten
            
        context.user_data['state'] = 'waiting_for_add_potensi_kategori'
        
        categories = get_all_distinct_categories()
        context.user_data['all_categories'] = categories
        
        keyboard = []
        for i, cat in enumerate(categories):
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"add_pot_cat:{site_id}:{i}")])
        keyboard.append([InlineKeyboardButton("❌ Batal", callback_data=f"site_opt:back_to_menu:{site_id}")])
        
        await query.edit_message_text(
            f"➕ *Tambah Potensi Site Baru*\n"
            f"Site ID: {site_id}\n"
            f"Branch: {branch if branch else '-'}\n"
            f"Cluster: {cluster if cluster else '-'}\n\n"
            f"Silakan pilih **Kategori** atau ketik kategori baru:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data.startswith("add_pot_cat:"):
        _, site_id, idx_str = data.split(":", 2)
        idx = int(idx_str)
        
        categories = context.user_data.get('all_categories', [])
        if not categories or idx >= len(categories):
            categories = get_all_distinct_categories()
            context.user_data['all_categories'] = categories
            
        if not categories or idx >= len(categories):
            await query.edit_message_text(
                "Terjadi kesalahan: Kategori tidak ditemukan.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Kembali", callback_data=f"site_opt:back_to_menu:{site_id}")]
                ])
            )
            return
            
        category = categories[idx]
        context.user_data['add_potensi_kategori'] = category
        context.user_data['state'] = 'waiting_for_add_potensi_nama'
        
        await query.edit_message_text(
            f"➕ *Tambah Potensi Site Baru*\n"
            f"Site ID: {site_id}\n"
            f"Kategori: *{category}*\n\n"
            f"Silakan masukkan **Nama Lokasi**:\n"
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
                f"Tidak ada data pelanggan yang perlu dikunjungi (Acq = 'N') untuk SITE ID {site_id}.",
                reply_markup=keyboard
            )
        else:
            context.user_data['state'] = None
            context.user_data['search_results'] = customers
            context.user_data['current_index'] = 0
            await show_customer_for_query(query, context)

    elif data.startswith("site_opt:back_to_menu:"):
        site_id = data.split(":", 2)[2]
        coords = get_site_coordinates(site_id)
        site_lat, site_lon = coords if coords else (None, None)
        maps_url = make_gmaps_url(site_lat, site_lon)
        maps_str = f"[📍 {site_lat},{site_lon} (Buka Google Maps)]({maps_url})" if maps_url else "-"
        await query.edit_message_text(
            f"SITE ID: {site_id}\n"
            f"Branch: {context.user_data.get('selected_branch', '-')}\n"
            f"Cluster: {context.user_data.get('selected_cluster', '-')}\n"
            f"Koordinat: {maps_str}\n\n"
            "Silakan pilih tindakan yang ingin dilakukan:",
            reply_markup=site_options_keyboard(site_id, site_lat, site_lon),
            parse_mode="Markdown"
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
    app.add_handler(MessageHandler((filters.TEXT | filters.LOCATION) & ~filters.COMMAND, handle_message))

    print("Bot sedang berjalan...")
    app.run_polling()
