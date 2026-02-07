# DCS C-130J Nav Injector

An external tool to inject custom waypoints into the **DCS: C-130J** `user_data.db`.

This utility allows you to input coordinates in various formats (Lat/Lon, MGRS, DDM, etc.) and inject them directly into the aircraft's navigation database without needing to manually punch them in via the CNI-MU.

## Features

- **Multi-Format Parsing**: Pasting coordinates from F10 Map, Google Maps, CombatFlite, or other planners.
  - *MGRS* (e.g., `38T PM 12345 67890`)
  - *Lat/Lon Decimal* (e.g., `42.351 -71.042`)
  - *DDM* (e.g., `N 42 21.06 W 071 02.52`)
  - *DMS* (e.g., `N 42 21 03 W 71 02 31`)
- **Smart Conversion**: Automatically converts all inputs to the specific format required by the C-130J CNI-MU.
- **Safety Checks**: Prevents "Zone Bug" crashes by forcing Lat/Lon format for MGRS zones divisible by 10 (e.g., 10T, 20T, 30T).
- **Database Backup**: Automatically creates a `.bak` backup of your `user_data.db` before every connection.
- **Manage Waypoints**: View, add, and delete custom waypoints via a clean GUI.

## Installation

1. **Download**: Clone or download this repository.
2. **Requirements** (if running from source):
   - Python 3.10+
   - `pip install -r requirements.txt`
3. **Location**: When you launch the application for the first time, you will be prompted to select your `user_data.db` file. It is typically located in:
   `%USERPROFILE%\Saved Games\DCS.C130J\user_data.db`
   
   **Configuration**: The tool remembers your last used database location in a local `config.json` file. You can change this at any time via **File > Open Database...**.

## Usage

1. **Launch**: Run `main.py`.
2. **Connect**: The tool will load your existing custom waypoints.
3. **Inject Data**:
   - **Name**: Enter a 1-5 character identifier (e.g., `DZ1`, `LZ2`).
   - **Coordinates**: Paste your coordinates into the input field. Examples:
     - `42.123, -71.456`
     - `38T HL 123 456`
     - `N42 15.5 W071 20.2`
   - **Preview**: Verify the parsed location in the preview label (Green = Valid).
   - **Click "INJECT DATA"**.
4. **In-Game**:
   - The waypoints will be available in the CUSTOM DATA.

## Notes & Known Issues

- **Elevation**: Due to a bug in the current C-130J simulation, injecting altitude often causes issues. This tool currently sets all elevations to `NULL` (sim defaults to ~6500ft or ground level logic) to ensure stability.
- **Zone Bug**: As mentioned in features, MGRS inputs for zones 10, 20, 30, etc., are automatically converted to Lat/Lon to avoid crashing the aircraft avionics.

## Disclaimer

This is a community modification and is not affiliated with the developers of the DCS C-130J module. Always back up your `Saved Games` folder.
