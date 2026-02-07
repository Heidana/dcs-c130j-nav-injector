import sys
import sqlite3
import shutil
import re
import mgrs  # pip install mgrs
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QTableWidget, QTableWidgetItem, QHeaderView, 
                               QMessageBox, QFileDialog, QGroupBox, QMenu)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPalette, QFont

# --- CONFIGURATION ---
DEFAULT_DB_PATH = Path.home() / "Saved Games" / "DCS.C130J" / "user_data.db"
BACKUP_EXTENSION = ".bak"
VERSION = "1.1.0"

# --- LOGIC CORE ---

class C130Format:
    """Handles the specific C-130J avionics string formatting."""
    
    @staticmethod
    def to_latlon_string(lat, lon):
        """
        Converts DD to CNI-MU format: Ndd^mm.mm Wddd^mm.mm
        Target: N52^00.00 W000^00.00 (Using ^ as safe delimiter)
        """
        def format_coord(value, is_lat):
            prefix = ('N' if value >= 0 else 'S') if is_lat else ('E' if value >= 0 else 'W')
            val = abs(value)
            degrees = int(val)
            minutes = (val - degrees) * 60.0
            
            # Width: Lat=2 digits (0-90), Lon=3 digits (0-180)
            deg_width = 2 if is_lat else 3
            
            # Format: PDD^MM.mm
            return f"{prefix}{degrees:0{deg_width}d}^{minutes:05.2f}"

        lat_str = format_coord(lat, True)
        lon_str = format_coord(lon, False)
        return f"{lat_str} {lon_str}"

    @staticmethod
    def generate_entry_pos(lat, lon):
        """
        Decides whether to use MGRS or Lat/Lon based on the 'Zone Bug'.
        Zones divisible by 10 (10, 20, 30...) crash the C-130 if input as MGRS.
        """
        m = mgrs.MGRS()
        try:
            # Generate MGRS with high precision (5 digits = 1m accuracy)
            mgrs_str = m.toMGRS(lat, lon, MGRSPrecision=5)
            # CRITICAL: Remove ALL spaces (Sim requirement: 33WVQ...)
            clean_mgrs = mgrs_str.replace(" ", "")
            
            # Extract Zone (first 1 or 2 digits)
            match = re.match(r"^(\d{1,2})[A-Z]", clean_mgrs)
            if match:
                zone = int(match.group(1))
                if zone % 10 == 0:
                    # Zone 10, 20, 30... Force Lat/Lon to prevent crash
                    return C130Format.to_latlon_string(lat, lon)
            
            return clean_mgrs # Return space-less MGRS if safe
            
        except Exception:
            # Fallback to Lat/Lon if MGRS fails
            return C130Format.to_latlon_string(lat, lon)

class SmartParser:
    """The regex waterfall to decode user input."""
    
    @staticmethod
    def parse(text):
        text = text.strip().upper()
        
        # 1. Combat Flite / DDM (N 25 06.333 E 056 20.417)
        pattern_ddm = r"([NS])\s*(\d+)[°\s\^]+(\d+(?:\.\d+)?)\'?\s*,?\s*([EW])\s*(\d+)[°\s\^]+(\d+(?:\.\d+)?)\'?"
        m = re.match(pattern_ddm, text)
        if m:
            return SmartParser._process_ddm(m.groups())

        # 2. FSE / Suffix DD (10.25N, 67.6498W)
        pattern_suffix = r"(\d+(?:\.\d+)?)\s*([NS]),?\s*(\d+(?:\.\d+)?)\s*([EW])"
        m = re.match(pattern_suffix, text)
        if m:
            lat, ns, lon, ew = m.groups()
            return SmartParser._finalize(float(lat), ns, float(lon), ew, "FSE/Suffix")

        # 3. DMS (N23 12 14 E 52 32 12)
        nums = re.findall(r"(\d+(?:\.\d+)?)", text)
        dirs = re.findall(r"([NSEW])", text)
        if len(nums) >= 6 and len(dirs) >= 2:
            d1, m1, s1 = float(nums[0]), float(nums[1]), float(nums[2])
            d2, m2, s2 = float(nums[3]), float(nums[4]), float(nums[5])
            lat_val = d1 + m1/60 + s1/3600
            lon_val = d2 + m2/60 + s2/3600
            ns = dirs[0] if dirs[0] in ['N','S'] else dirs[1]
            ew = dirs[1] if dirs[1] in ['E','W'] else dirs[0]
            return SmartParser._finalize(lat_val, ns, lon_val, ew, "DMS Standard")

        # 4. Google Maps / Simple DD (23.241, -83.424)
        pattern_dd = r"(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)$"
        m = re.match(pattern_dd, text)
        if m:
            lat, lon = map(float, m.groups())
            return {'lat': lat, 'lon': lon, 'type': 'Decimal Degrees'}

        # 5. MGRS (Fallback)
        if re.match(r"^\d{1,2}[A-Z]", text):
            try:
                m = mgrs.MGRS()
                clean_text = text.replace(" ", "") # Sanitize input
                lat, lon = m.toLatLon(clean_text)
                return {'lat': lat, 'lon': lon, 'type': 'MGRS Input'}
            except:
                pass

        return None

    @staticmethod
    def _process_ddm(groups):
        ns, d1, m1, ew, d2, m2 = groups
        lat = float(d1) + float(m1)/60.0
        lon = float(d2) + float(m2)/60.0
        return SmartParser._finalize(lat, ns, lon, ew, "DDM")

    @staticmethod
    def _finalize(lat, ns, lon, ew, type_name):
        if ns == 'S': lat = -lat
        if ew == 'W': lon = -lon
        return {'lat': lat, 'lon': lon, 'type': type_name}

# --- DATABASE MANAGER ---

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self):
        if not self.db_path.exists():
            return False, "Database file not found."
        try:
            backup_path = self.db_path.with_suffix(self.db_path.suffix + BACKUP_EXTENSION)
            shutil.copy2(self.db_path, backup_path)
        except Exception as e:
            return False, f"Backup failed: {e}"

        try:
            self.conn = sqlite3.connect(self.db_path)
            return True, "Connected."
        except Exception as e:
            return False, str(e)

    def get_waypoints(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, entry_pos, lat, lon FROM custom_data")
        return cursor.fetchall()

    def add_waypoint(self, name, entry_pos, lat, lon):
        cursor = self.conn.cursor()
        try:
            # CHANGED: Now inserts None (NULL) for altitude
            cursor.execute(
                "INSERT INTO custom_data (name, entry_pos, lat, lon, alt) VALUES (?, ?, ?, ?, ?)",
                (name, entry_pos, lat, lon, None)
            )
            self.conn.commit()
            return True, ""
        except sqlite3.IntegrityError:
            return False, "Waypoint Name already exists."
        except Exception as e:
            return False, str(e)

    def delete_waypoint(self, name):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM custom_data WHERE name = ?", (name,))
        self.conn.commit()

# --- GUI ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"C-130J Nav Injector v{VERSION}")
        self.resize(1000, 600)
        self.apply_dark_theme()
        
        self.db = None
        self.setup_ui()
        self.init_db()

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        self.setPalette(palette)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        # LEFT: Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Entry String (C-130)", "Lat", "Lon"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        layout.addWidget(self.table, 70)

        # RIGHT: Input
        right_panel = QGroupBox("Add New Waypoint")
        right_layout = QVBoxLayout(right_panel)
        
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Name (Max 5 Chars)")
        
        self.input_coords = QLineEdit()
        self.input_coords.setPlaceholderText("Paste (MGRS, DDM, Lat/Lon...)")
        self.input_coords.textChanged.connect(self.on_coords_changed)
        
        self.lbl_preview = QLabel("Waiting for input...")
        self.lbl_preview.setStyleSheet("color: #888;")
        
        # Disclaimer Label
        lbl_disclaimer = QLabel("NOTE: Elevation defaults to 6562ft (NULL) due to Sim Bug.")
        lbl_disclaimer.setStyleSheet("color: #FFA500; font-size: 10px;")

        btn_add = QPushButton("INJECT DATA")
        btn_add.setMinimumHeight(50)
        btn_add.setStyleSheet("background-color: #2A82DA; font-weight: bold;")
        btn_add.clicked.connect(self.add_point)

        right_layout.addWidget(QLabel("Name (5 Char Max):"))
        right_layout.addWidget(self.input_name)
        right_layout.addWidget(QLabel("Coordinates:"))
        right_layout.addWidget(self.input_coords)
        right_layout.addWidget(self.lbl_preview)
        right_layout.addSpacing(10)
        right_layout.addWidget(lbl_disclaimer)
        right_layout.addStretch()
        right_layout.addWidget(btn_add)

        layout.addWidget(right_panel, 30)

    def init_db(self):
        path = DEFAULT_DB_PATH
        if not path.exists():
            file_dialog = QFileDialog(self, "Locate C-130J user_data.db", str(Path.home()))
            file_dialog.setNameFilter("Database (*.db)")
            if file_dialog.exec():
                path = Path(file_dialog.selectedFiles()[0])
            else:
                sys.exit() 

        self.db = DatabaseManager(path)
        success, msg = self.db.connect()
        if success:
            self.refresh_table()
        else:
            QMessageBox.critical(self, "Error", msg)

    def on_coords_changed(self, text):
        if not text:
            self.lbl_preview.setText("Waiting...")
            return
        
        result = SmartParser.parse(text)
        if result:
            self.lbl_preview.setText(f"✓ {result['type']}\nLat: {result['lat']:.5f}\nLon: {result['lon']:.5f}")
            self.lbl_preview.setStyleSheet("color: #0f0;") 
        else:
            self.lbl_preview.setText("⚠ Unknown Format")
            self.lbl_preview.setStyleSheet("color: #f00;") 

    def add_point(self):
        name = self.input_name.text().strip().upper()
        raw_coords = self.input_coords.text()

        if not name:
            QMessageBox.warning(self, "Input Error", "Name is required.")
            return
        if len(name) > 5:
            QMessageBox.warning(self, "Input Error", "Name cannot exceed 5 characters.")
            return

        parsed = SmartParser.parse(raw_coords)
        if not parsed:
            QMessageBox.warning(self, "Input Error", "Could not decipher coordinates.")
            return
        
        lat, lon = parsed['lat'], parsed['lon']
        entry_pos = C130Format.generate_entry_pos(lat, lon)

        success, msg = self.db.add_waypoint(name, entry_pos, lat, lon)
        if success:
            self.refresh_table()
            self.input_name.clear()
            self.input_coords.clear()
            self.lbl_preview.setText("Waiting...")
            QMessageBox.information(self, "Success", f"Point {name} injected!\nEntry: {entry_pos}")
        else:
            QMessageBox.critical(self, "Database Error", msg)

    def refresh_table(self):
        self.table.setRowCount(0)
        data = self.db.get_waypoints()
        for row_idx, (name, entry, lat, lon) in enumerate(data):
            self.table.insertRow(row_idx)
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(name)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(entry)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{lat:.6f}"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(f"{lon:.6f}"))

    def open_context_menu(self, position):
        menu = QMenu()
        delete_action = QAction("Delete Waypoint", self)
        delete_action.triggered.connect(self.delete_selected)
        menu.addAction(delete_action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def delete_selected(self):
        row = self.table.currentRow()
        if row >= 0:
            name = self.table.item(row, 0).text()
            confirm = QMessageBox.question(self, "Confirm", f"Delete {name}?", QMessageBox.Yes | QMessageBox.No)
            if confirm == QMessageBox.Yes:
                self.db.delete_waypoint(name)
                self.refresh_table()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())