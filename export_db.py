import csv
import os
import pymysql
from db_init import get_db_connection, DB_TYPE

def export_table():
    if DB_TYPE != 'mysql':
        print("Script ini dikonfigurasi untuk export database MySQL.")
        return
        
    print("Menghubungkan ke MySQL untuk mengekspor tabel...")
    try:
        conn = get_db_connection()
        # We can use either DictCursor or default cursor
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Ambil struktur kolom
        cursor.execute("DESCRIBE customers")
        columns = [row['Field'] for row in cursor.fetchall()]
        
        # Ambil semua data pelanggan
        cursor.execute("SELECT * FROM customers")
        rows = cursor.fetchall()
        
        filename = "exported_customers.csv"
        with open(filename, mode='w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
            
        print(f"Berhasil! Mengekspor {len(rows)} data pelanggan ke file: {filename}")
        conn.close()
    except Exception as e:
        print(f"Gagal mengekspor data: {e}")

if __name__ == '__main__':
    export_table()
