import os
import sqlite3
import pymysql
import time
import logging

logger = logging.getLogger(__name__)

def clean_val(val):
    if not val:
        return val
    return str(val).strip().strip('"').strip("'").strip()

def get_mysql_config():
    # Local Docker MySQL defaults
    host = 'db'
    port = 3306
    user = 'botuser'
    password = 'botpassword'
    database = 'botsite'

    # Support connection URL format (mysql://user:pass@host:port/db) if provided
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

    # Explicit environment variable overrides (preferred for Docker / Local Server)
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

def get_db_type():
    db_type_env = os.environ.get('DB_TYPE')
    if db_type_env:
        return db_type_env.lower()
    
    # Check if SQLite is explicitly requested
    if os.environ.get('USE_SQLITE') == '1':
        return 'sqlite'
        
    return 'mysql'

DB_TYPE = get_db_type()
PLACEHOLDER = '%s' if DB_TYPE == 'mysql' else '?'

def get_db_connection(retries=15, delay=3, as_dict=False):
    if DB_TYPE == 'mysql':
        host, port, user, password, database = get_mysql_config()
        logger.info(f"Connecting to MySQL: host={host}, port={port}, user={user}, database={database}")
        
        last_error = None
        for i in range(retries):
            try:
                kw = {
                    'host': host,
                    'port': port,
                    'user': user,
                    'password': password,
                    'database': database,
                    'autocommit': True
                }
                if as_dict:
                    kw['cursorclass'] = pymysql.cursors.DictCursor
                conn = pymysql.connect(**kw)
                return conn
            except Exception as e:
                last_error = e
                logger.warning(f"Connecting to MySQL failed (attempt {i+1}/{retries}): {e}")
                time.sleep(delay)
        raise Exception(f"Could not connect to MySQL server at {host}:{port}") from last_error
    else:
        conn = sqlite3.connect('database.db')
        if as_dict:
            conn.row_factory = sqlite3.Row
        return conn

