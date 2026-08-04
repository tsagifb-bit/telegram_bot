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
    cust_count = is_table_populated(cursor, 'customers')
    if cust_count > 0 and not force_reinit:
        print(f"customers table already initialized. Found {cust_count} entries. Skipping CSV import to preserve user updates.", flush=True)
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                bb_id VARCHAR(255) PRIMARY KEY,
                Latitude VARCHAR(255),
                Longitude VARCHAR(255),
                Nearest_Site_ID VARCHAR(255),
                Distance_km DOUBLE,
                Branch VARCHAR(255),
                Cluster VARCHAR(255),
                Cat VARCHAR(255),
                Focus VARCHAR(255),
                Opt VARCHAR(255),
                Opt2 VARCHAR(255),
                Cat_Site VARCHAR(255),
                Nama VARCHAR(255),
                No_HP VARCHAR(255),
                Alamat TEXT,
                Kodepos VARCHAR(20),
                Acq VARCHAR(10),
                nomor_baru_pelanggan VARCHAR(255)
            )
        ''')
        
        # Create indexes for optimization
        if DB_TYPE == 'sqlite':
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_site_id ON customers(Nearest_Site_ID)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_branch ON customers(Branch)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cluster ON customers(Cluster)')
        else:
            for idx_name, col in [('idx_site_id', 'Nearest_Site_ID'), ('idx_branch', 'Branch'), ('idx_cluster', 'Cluster')]:
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
                        bb_id, Latitude, Longitude, Nearest_Site_ID, Distance_km,
                        Branch, Cluster, Cat, Focus, Opt, Opt2, Cat_Site,
                        Nama, No_HP, Alamat, Kodepos, Acq
                    ) VALUES ({", ".join([PLACEHOLDER] * 17)})
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
                    cat_site = row[12].strip() if len(row) > 12 else ''
                    nama = row[13].strip() if len(row) > 13 else ''
                    no_hp = row[14].strip() if len(row) > 14 else ''
                    alamat = row[15].strip() if len(row) > 15 else ''
                    kodepos = row[16].strip() if len(row) > 16 else ''
                    acq = row[17].strip() if len(row) > 17 else ''
                    
                    cursor.execute(insert_query, (
                        bb_id, latitude, longitude, nearest_site_id, distance_km,
                        branch, cluster, cat, focus, opt, opt2, cat_site,
                        nama, no_hp, alamat, kodepos, acq
                    ))
                    rows_inserted += 1
                    
            conn.commit()
            print(f"Customers database initialized. Imported {rows_inserted} rows.", flush=True)

    # 2. Initialize potensi_site
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
                longitude DOUBLE,
                latitude DOUBLE,
                distance_km DOUBLE
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
                        branch, cluster, longitude, latitude, distance_km
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
    focus_count = is_table_populated(cursor, 'site_focus')
    if focus_count > 0 and not force_reinit:
        print(f"site_focus table already initialized. Found {focus_count} entries. Skipping CSV import.", flush=True)
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS site_focus (
                no INT PRIMARY KEY,
                site VARCHAR(255),
                site_name VARCHAR(255),
                branch VARCHAR(255),
                cluster VARCHAR(255),
                kabupaten VARCHAR(255),
                kecamatan VARCHAR(255),
                latitude DOUBLE,
                longitude DOUBLE
            )
        ''')
        
        # Create index on site
        if DB_TYPE == 'sqlite':
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_site_focus_site ON site_focus(site)')
        else:
            try:
                cursor.execute('CREATE INDEX idx_site_focus_site ON site_focus(site)')
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
                        no, site, site_name, branch, cluster,
                        kabupaten, kecamatan, latitude, longitude
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
                        
                    site = row[1].strip()
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
                        no, site, site_name, branch, cluster,
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
