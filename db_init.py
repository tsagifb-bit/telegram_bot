import os
import csv
import sqlite3
import pymysql
import time

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
            print(f"Failed to parse connection URL: {e}", flush=True)

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
        print(f"Connecting to MySQL with: host={host}, port={port}, user={user}, database={database}", flush=True)
        
        last_error = None
        # Retry logic for MySQL connection (essential for container startup)
        for i in range(15):
            try:
                conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    autocommit=True
                )
                return conn
            except Exception as e:
                last_error = e
                print(f"Connecting to MySQL failed (attempt {i+1}/15): {e}", flush=True)
                time.sleep(3)
        raise Exception("Could not connect to MySQL server") from last_error
    else:
        return sqlite3.connect('database.db')

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
    
    # 1. Initialize customers
    customers_initialized = False
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM customers")
        row = cursor.fetchone()
        if row:
            count = row['total'] if isinstance(row, dict) else row[0]
            if count > 0:
                print(f"Customers table already initialized. Found {count} customers. Skipping customers import.")
                customers_initialized = True
    except Exception:
        pass

    if not customers_initialized:
        # Create table (compatible syntax for both MySQL and SQLite)
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
            # For MySQL, we run CREATE INDEX and catch exceptions if index already exists
            for idx_name, col in [('idx_site_id', 'Nearest_Site_ID'), ('idx_branch', 'Branch'), ('idx_cluster', 'Cluster')]:
                try:
                    cursor.execute(f'CREATE INDEX {idx_name} ON customers({col})')
                except Exception:
                    pass
        
        # Import CSV data
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
        print(f"Customers database initialized. Imported {rows_inserted} rows.")

    # 2. Initialize potensi_site
    potensi_site_initialized = False
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM potensi_site")
        row = cursor.fetchone()
        if row:
            count = row['total'] if isinstance(row, dict) else row[0]
            if count > 0:
                print(f"potensi_site table already initialized. Found {count} entries. Skipping potensi_site import.")
                potensi_site_initialized = True
    except Exception:
        pass

    if not potensi_site_initialized:
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
            print(f"potensi_site database initialized. Imported {rows_inserted} rows.")
        else:
            print("potensi_site.csv not found, skipping import.")
            
    # 3. Initialize site_focus
    # Force drop and recreate to ensure updated schema with Branch and Cluster columns is applied.
    try:
        cursor.execute("DROP TABLE IF EXISTS site_focus")
    except Exception:
        pass

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
            header = next(reader) # skip header: No,Site,Site Name,Branch,Cluster,Kabupaten,Kecamatan,Latitdue,Longitude
            
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
        print(f"site_focus database initialized. Imported {rows_inserted} rows.")
    else:
        print("site_focus.csv not found, skipping import.")
            
    conn.close()

if __name__ == '__main__':
    init_db()
