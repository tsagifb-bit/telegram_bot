import os
import csv
import logging
from db import get_db_connection, DB_TYPE, PLACEHOLDER

logger = logging.getLogger(__name__)

def is_table_populated(cursor, table_name):
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row = cursor.fetchone()
        if row:
            count = row[0]
            return count if count > 0 else 0
    except Exception:
        pass
    return 0

def init_db():
    print("=== DUMPING ENVIRONMENT VARIABLES ===", flush=True)
    for k, v in sorted(os.environ.items()):
        if any(sec in k.upper() for sec in ['PASS', 'KEY', 'SECRET', 'TOKEN', 'AUTH']):
            print(f"  {k} = [MASKED]", flush=True)
        else:
            print(f"  {k} = {v}", flush=True)
    print("===================================", flush=True)

    conn = get_db_connection()
    cursor = conn.cursor()
    force_reinit = os.environ.get('FORCE_REINIT_DB') == '1'
    
    # 1. Initialize customers
    if force_reinit:
        try:
            cursor.execute("DROP TABLE IF EXISTS customers")
        except Exception:
            pass
    cust_count = is_table_populated(cursor, 'customers')
    if cust_count > 0 and not force_reinit:
        print(f"customers table already initialized. Found {cust_count} entries. Skipping CSV import to preserve user updates.", flush=True)
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                bb_id VARCHAR(255) PRIMARY KEY,
                lat VARCHAR(255),
                long VARCHAR(255),
                site_id VARCHAR(255),
                distance DOUBLE,
                branch VARCHAR(255),
                cluster VARCHAR(255),
                cat VARCHAR(255),
                focus VARCHAR(255),
                opt_location VARCHAR(255),
                opt_name VARCHAR(255),
                cat_site VARCHAR(255),
                nama VARCHAR(255),
                no_hp VARCHAR(255),
                alamat TEXT,
                kodepos VARCHAR(20),
                acq VARCHAR(10),
                nomor_baru VARCHAR(255)
            )
        ''')
        
        # Create indexes for optimization
        if DB_TYPE == 'sqlite':
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_site_id ON customers(site_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_branch ON customers(branch)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cluster ON customers(cluster)')
        else:
            for idx_name, col in [('idx_site_id', 'site_id'), ('idx_branch', 'branch'), ('idx_cluster', 'cluster')]:
                try:
                    cursor.execute(f'CREATE INDEX {idx_name} ON customers({col})')
                except Exception:
                    pass
        
        # Import Book1.csv data
        if os.path.exists('Book1.csv'):
            with open('Book1.csv', mode='r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.reader(f)
                header = next(reader) # skip header
                
                insert_query = f'''
                    REPLACE INTO customers (
                        bb_id, lat, long, site_id, distance,
                        branch, cluster, cat, focus, opt_location, opt_name, cat_site,
                        nama, no_hp, alamat, kodepos, acq, nomor_baru
                    ) VALUES ({", ".join([PLACEHOLDER] * 18)})
                '''
                
                rows_inserted = 0
                for row in reader:
                    if not row or len(row) < 17:
                        continue
                    
                    bb_id = row[0].strip()
                    if not bb_id:
                        continue
                        
                    latitude = row[1].strip()
                    longitude = row[2].strip()
                    nearest_site_id = row[3].strip()
                    try:
                        distance_km = float(row[4].strip()) if row[4].strip() else 0.0
                    except ValueError:
                        distance_km = 0.0
                    branch = row[5].strip()
                    cluster = row[6].strip()
                    cat = row[7].strip()
                    focus = row[8].strip()
                    opt = row[9].strip()
                    opt2 = row[10].strip() if len(row) > 10 else ''
                    cat_site = row[11].strip() if len(row) > 11 else ''
                    nama = row[12].strip() if len(row) > 12 else ''
                    no_hp = row[13].strip() if len(row) > 13 else ''
                    alamat = row[14].strip() if len(row) > 14 else ''
                    kodepos = row[15].strip() if len(row) > 15 else ''
                    acq = row[16].strip() if len(row) > 16 else ''
                    nomor_baru = row[17].strip() if len(row) > 17 else ''
                    cursor.execute(insert_query, (
                        bb_id, latitude, longitude, nearest_site_id, distance_km,
                        branch, cluster, cat, focus, opt, opt2, cat_site,
                        nama, no_hp, alamat, kodepos, acq, nomor_baru
                    ))
                    rows_inserted += 1
                    
            conn.commit()
            print(f"Customers database initialized. Imported {rows_inserted} rows.", flush=True)

    # 2. Initialize potensi_site
    if force_reinit:
        try:
            cursor.execute("DROP TABLE IF EXISTS potensi_site")
        except Exception:
            pass
    pot_count = is_table_populated(cursor, 'potensi_site')
    if pot_count > 0 and not force_reinit:
        print(f"potensi_site table already initialized. Found {pot_count} entries. Skipping CSV import to preserve user updates.", flush=True)
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS potensi_site (
                no INT PRIMARY KEY,
                site_id VARCHAR(255),
                nama VARCHAR(255),
                kategori VARCHAR(255),
                kabupaten VARCHAR(255),
                branch VARCHAR(255),
                cluster VARCHAR(255),
                long DOUBLE,
                lat DOUBLE,
                distance DOUBLE
            )
        ''')
        
        # Create index on site_id
        if DB_TYPE == 'sqlite':
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_potensi_site_id ON potensi_site(site_id)')
        else:
            try:
                cursor.execute('CREATE INDEX idx_potensi_site_id ON potensi_site(site_id)')
            except Exception:
                pass
                
        # Import potensi_site.csv data
        potensi_site_csv_path = 'potensi_site.csv'
        if os.path.exists(potensi_site_csv_path):
            with open(potensi_site_csv_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.reader(f)
                header = next(reader) # skip header
                
                insert_query = f'''
                    REPLACE INTO potensi_site (
                        no, site_id, nama, kategori, kabupaten,
                        branch, cluster, long, lat, distance
                    ) VALUES ({", ".join([PLACEHOLDER] * 10)})
                '''
                
                rows_inserted = 0
                for row in reader:
                    if not row or len(row) < 10:
                        continue
                    
                    try:
                        no = int(row[0].strip())
                    except ValueError:
                        continue
                        
                    site_id = row[1].strip()
                    nama = row[2].strip()
                    kategori = row[3].strip()
                    kabupaten = row[4].strip()
                    branch = row[5].strip()
                    cluster = row[6].strip()
                    
                    try:
                        longitude = float(row[7].strip()) if row[7].strip() else 0.0
                    except ValueError:
                        longitude = 0.0
                        
                    try:
                        latitude = float(row[8].strip()) if row[8].strip() else 0.0
                    except ValueError:
                        latitude = 0.0
                        
                    try:
                        distance_km = float(row[9].strip()) if row[9].strip() else 0.0
                    except ValueError:
                        distance_km = 0.0
                    
                    cursor.execute(insert_query, (
                        no, site_id, nama, kategori, kabupaten,
                        branch, cluster, longitude, latitude, distance_km
                    ))
                    rows_inserted += 1
                    
            conn.commit()
            print(f"potensi_site database initialized. Imported {rows_inserted} rows.", flush=True)
        else:
            print("potensi_site.csv not found, skipping import.", flush=True)

    # 3. Initialize site_focus
    if force_reinit:
        try:
            cursor.execute("DROP TABLE IF EXISTS site_focus")
        except Exception:
            pass
    focus_count = is_table_populated(cursor, 'site_focus')
    if focus_count > 0 and not force_reinit:
        print(f"site_focus table already initialized. Found {focus_count} entries. Skipping CSV import.", flush=True)
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_focus (
                no INT PRIMARY KEY,
                site_id VARCHAR(255),
                site_name VARCHAR(255),
                branch VARCHAR(255),
                cluster VARCHAR(255),
                kabupaten VARCHAR(255),
                kecamatan VARCHAR(255),
                lat DOUBLE,
                long DOUBLE
            )
        ''')
        
        # Create index on site_id
        if DB_TYPE == 'sqlite':
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_site_focus_site ON site_focus(site_id)')
        else:
            try:
                cursor.execute('CREATE INDEX idx_site_focus_site ON site_focus(site_id)')
            except Exception:
                pass
                
        # Import site_focus.csv data
        site_focus_csv_path = 'site_focus.csv'
        if os.path.exists(site_focus_csv_path):
            with open(site_focus_csv_path, mode='r', encoding='utf-8-sig', errors='ignore') as f:
                reader = csv.reader(f)
                header = next(reader) # skip header
                
                insert_query = f'''
                    REPLACE INTO site_focus (
                        no, site_id, site_name, branch, cluster,
                        kabupaten, kecamatan, lat, long
                    ) VALUES ({", ".join([PLACEHOLDER] * 9)})
                '''
                
                rows_inserted = 0
                for row in reader:
                    if not row or len(row) < 9:
                        continue
                    
                    try:
                        no = int(row[0].strip())
                    except ValueError:
                        continue
                        
                    site_id = row[1].strip()
                    site_name = row[2].strip()
                    branch = row[3].strip()
                    cluster = row[4].strip()
                    kabupaten = row[5].strip()
                    kecamatan = row[6].strip()
                    
                    try:
                        latitude = float(row[7].strip()) if row[7].strip() else 0.0
                    except ValueError:
                        latitude = 0.0
                        
                    try:
                        longitude = float(row[8].strip()) if row[8].strip() else 0.0
                    except ValueError:
                        longitude = 0.0
                    
                    cursor.execute(insert_query, (
                        no, site_id, site_name, branch, cluster,
                        kabupaten, kecamatan, latitude, longitude
                    ))
                    rows_inserted += 1
                    
            conn.commit()
            print(f"site_focus database initialized. Imported {rows_inserted} rows.", flush=True)
        else:
            print("site_focus.csv not found, skipping import.", flush=True)
            
    conn.close()

if __name__ == '__main__':
    init_db()
