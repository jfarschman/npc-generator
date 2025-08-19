import json
import os
from pathlib import Path

# --- CONFIGURATION ---
# This script assumes it's in the same folder as your 'json' directory
JSON_DIR = Path(__file__).parent / "json"
OUTPUT_FILENAME = "kanka_id_map.json"

def get_name_and_id(file_path):
    """Reads a Kanka export file and returns the name and correct top-level ID."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # The top-level ID is what the API needs for linking
        kanka_id = data.get("id")
        # The entity name is nested inside the 'entity' object
        name = data.get("entity", {}).get("name")

        if kanka_id and name:
            return name, kanka_id
    except Exception as e:
        print(f"  - Warning: Could not process file {file_path.name}. Error: {e}")
    return None, None

def generate_map_from_subfolder(subfolder_path):
    """Scans a subfolder and creates a dictionary of name:id pairs."""
    id_map = {}
    print(f"Scanning '{subfolder_path.name}' directory...")
    
    if not subfolder_path.is_dir():
        print(f"  - Directory not found. Skipping.")
        return {}

    for file_path in subfolder_path.glob("*.json"):
        name, kanka_id = get_name_and_id(file_path)
        if name and kanka_id:
            id_map[name] = kanka_id
            print(f"  - Found: '{name}' -> {kanka_id}")
    return id_map

# --- Main execution block ---
if __name__ == "__main__":
    print("Starting Kanka ID Map generation...\n")
    
    # Define the paths to your lore folders
    locations_path = JSON_DIR / "hometowns"
    races_path = JSON_DIR / "races"
    orgs_path = JSON_DIR / "organizations"

    # Generate the map for each category
    final_map = {
        "races": generate_map_from_subfolder(races_path),
        "locations": generate_map_from_subfolder(locations_path),
        "organizations": generate_map_from_subfolder(orgs_path)
    }

    # Save the complete map to the output file
    output_path = JSON_DIR / OUTPUT_FILENAME
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_map, f, indent=2)
        print(f"\nSuccess! New '{OUTPUT_FILENAME}' has been generated in your 'json' directory.")
    except Exception as e:
        print(f"\nError: Could not write the final output file. {e}")
