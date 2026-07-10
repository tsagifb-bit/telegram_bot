import os
import csv
import sqlite3
import pymysql
import time

def get_mysql_config():
    host = 'localhost'
    port = 3306
    user = 'botuser'
    password = 'botpassword'
    database = 'botsite'

    # Try to parse from URL first (common on Railway)
    url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
    if url and url.startswith('mysql://'):
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
        except Exception as e:
            print(f"Failed to parse connection URL: {e}", flush=True)

    # Allow overlay with individual environment variables
    host = os.environ.get('DB_HOST') or os.environ.get('MYSQLHOST') or os.environ.get('MYSQL_HOST') or host
    port_val = os.environ.get('DB_PORT') or os.environ.get('MYSQLPORT') or os.environ.get('MYSQL_PORT')
    if port_val:
        try:
            port = int(port_val)
        except ValueError:
            pass
    user = os.environ.get('DB_USER') or os.environ.get('MYSQLUSER') or os.environ.get('MYSQL_USER') or user
    password = os.environ.get('DB_PASSWORD') or os.environ.get('MYSQLPASSWORD') or os.environ.get('MYSQL_PASSWORD') or password
    database = os.environ.get('DB_DATABASE') or os.environ.get('MYSQLDATABASE') or os.environ.get('MYSQL_DATABASE') or os.environ.get('MYSQL_DB') or database

    return host, port, user, password, database

# DB Type detection
DB_TYPE = os.environ.get('DB_TYPE')
if not DB_TYPE:
    url = os.environ.get('MYSQL_URL') or os.environ.get('DATABASE_URL')
    is_mysql_url = url and url.startswith('mysql://')
    has_mysql_env = (
        os.environ.get('MYSQLHOST') or 
        os.environ.get('MYSQL_HOST') or 
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if table already has data
    try:
        cursor.execute("SELECT COUNT(*) AS total FROM customers")
        row = cursor.fetchone()
        if row:
            count = row['total'] if isinstance(row, dict) else row[0]
            if count > 0:
                print(f"Database already initialized. Found {count} customers. Skipping import.")
                conn.close()
                return
    except Exception:
        # Table might not exist yet, proceed to create it
        pass
    
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
    conn.close()
    print(f"Database initialized. Imported {rows_inserted} rows.")

if __name__ == '__main__':
    init_db()
