import sqlite3
import os
from pathlib import Path

# --- CONFIGURATION ---
# Standard Path
DB_PATH = Path.home() / "Saved Games" / "DCS.C130J" / "user_data.db"

# The "Control" Coordinate (Baghdad Intl - Zone 38)
# We use this for ALL points to keep variables constant.
TEST_COORD_MGRS = "38TPM3046282643" 
TEST_LAT = 33.2625
TEST_LON = 44.2325

# Test Cases: (Name, Feet_Input)
# Name must be 5 chars max!
TEST_POINTS = [
    ("A_ZER", 0),         # Baseline: 0 ft
    ("A_ONE", 1),         # Low Positive: 1 ft
    ("A_100", 100),       # Standard: 100 ft
    ("A_1K",  1000),      # Standard: 1,000 ft
    ("A_5K",  5000),      # Mid Alt: 5,000 ft
    ("A_10K", 10000),     # High Alt: 10,000 ft
    ("A_NEG", -1),        # Negative: -1 ft
    ("A_N1K", -1000),     # Deep Negative: -1,000 ft
    ("A_MAG", -0.1),      # The "Magic Number" theory (Ground Level?)
    ("A_MAX", 50000),     # Ceiling Test: 50,000 ft
]

def inject_calibration_data():
    print(f"[-] TARGET DATABASE: {DB_PATH}")
    
    if not DB_PATH.exists():
        print(f"[!] CRITICAL: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print("[-] CONNECTION ESTABLISHED.\n")

        print(f"{'NAME':<8} | {'INPUT (FT)':<12} | {'INJECTED (M)':<15}")
        print("-" * 45)

        for name, ft_val in TEST_POINTS:
            # 1. Convert Feet to Meters (Standard Aviation Conversion)
            # Logic: Maybe DCS uses meters internally?
            m_val = ft_val * 0.3048
            
            # 2. Delete if exists (Cleanup previous runs)
            cursor.execute("DELETE FROM custom_data WHERE name = ?", (name,))
            
            # 3. Insert fresh
            cursor.execute(
                "INSERT INTO custom_data (name, entry_pos, lat, lon, alt) VALUES (?, ?, ?, ?, ?)",
                (name, TEST_COORD_MGRS, TEST_LAT, TEST_LON, m_val)
            )
            
            print(f"{name:<8} | {ft_val:<12} | {m_val:<15.4f}")

        conn.commit()
        print("-" * 45)
        print("[-] INJECTION COMPLETE. LAUNCH SIM.")

    except sqlite3.Error as e:
        print(f"[!] SQLITE ERROR: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    inject_calibration_data()