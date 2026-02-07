import sqlite3
import os

# --- CONFIGURATION ---
DB_PATH = os.path.join(os.path.expanduser("~"), "Saved Games", "DCS.C130J", "user_data.db")

def sniper_probe():
    print(f"[-] TARGET LOCK: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print(f"[!] CRITICAL: Database file not found.")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print("[-] CONNECTION ESTABLISHED.\n")

        # Target specific test points
        targets = ('ALT01', 'BADZN', 'PRECI')
        query = f"SELECT * FROM custom_data WHERE name IN {targets}"
        
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            print("[!] WARNING: No test targets found. Did you save them in the CNI-MU?")
            return

        print(f"{'NAME':<10} {'ENTRY_POS (The string)':<25} {'LAT':<15} {'LON':<15} {'ALT'}")
        print("-" * 80)
        
        for row in rows:
            # Unpack based on known schema: name, entry_pos, lat, lon, alt
            name, entry, lat, lon, alt = row
            print(f"{name:<10} {str(entry):<25} {lat:<15.8f} {lon:<15.8f} {alt}")

    except sqlite3.Error as e:
        print(f"[!] SQLITE ERROR: {e}")
    finally:
        if conn:
            conn.close()
            print("\n[-] PROBE COMPLETE.")

if __name__ == "__main__":
    sniper_probe()