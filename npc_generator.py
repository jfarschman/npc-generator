import json
import os
import re
import secrets  # <-- Added missing import
import requests
import random
from pathlib import Path

# --- CONFIGURATION ---
JSON_DIR = Path(__file__).parent / "json"

# --- Kanka API Configuration ---
POST_TO_KANKA = False # Set to True to enable Kanka posting
KANKA_API_TOKEN = "YOUR_PERSONAL_API_TOKEN" 
CAMPAIGN_ID = 0 # Replace 0 with your campaign's ID

# --- Local LLM Configuration ---
LLM_API_URL = "http://localhost:11434/api/generate"
LLM_MODEL_NAME = "phi3:mini"

# --- D&D 5e Stat Blocks (for fvtt output) ---
STAT_BLOCKS_5E = {
    "commoner": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10, "hp": 4, "ac": 10},
    "guard": {"str": 13, "dex": 12, "con": 12, "int": 10, "wis": 11, "cha": 10, "hp": 11, "ac": 16},
    "mage": {"str": 9, "dex": 14, "con": 11, "int": 16, "wis": 12, "cha": 11, "hp": 9, "ac": 12},
}

# --- Daggerheart Stat Blocks (for dh output) ---
DAGGERHEART_STATS = {
    "commoner": {
        "difficulty": 10, "hp": 2, "stress": 3, "type": "social", "tier": 1,
        "thresholds": {"major": 3, "severe": 6},
        "attack": {"name": "Unarmed", "bonus": 0, "damage": "1d4"},
        "experience": {"name": "Local Lore", "value": 2}
    },
    "guard": {
        "difficulty": 13, "hp": 4, "stress": 4, "type": "physical", "tier": 1,
        "thresholds": {"major": 4, "severe": 8},
        "attack": {"name": "Sword", "bonus": 2, "damage": "1d8+2"},
        "experience": {"name": "Soldiering", "value": 3}
    },
    "mage": {
        "difficulty": 14, "hp": 3, "stress": 5, "type": "magical", "tier": 1,
        "thresholds": {"major": 4, "severe": 8},
        "attack": {"name": "Magic Bolt", "bonus": 3, "damage": "1d10"},
        "experience": {"name": "Arcana", "value": 4}
    },
    "noble": {
        "difficulty": 12, "hp": 3, "stress": 4, "type": "social", "tier": 1,
        "thresholds": {"major": 4, "severe": 8},
        "attack": {"name": "Dagger", "bonus": 1, "damage": "1d6+1"},
        "experience": {"name": "Etiquette", "value": 3}
    }
}

class NPCEngine:
    def __init__(self, data_path):
        self.data_path = data_path
        self.load_all_data()

    def _generate_id(self, length=16):
        """Generates a random alphanumeric string for Foundry IDs."""
        return secrets.token_hex(length // 2)

    def load_all_data(self):
        print("Loading world data...")
        self.rulebook = self._load_json(self.data_path / "world_connections.json")
        if POST_TO_KANKA: self.kanka_ids = self._load_json(self.data_path / "kanka_id_map.json")
        self.personality_traits = self._load_json(self.data_path / "personality_traits.json")['traits']
        self.ideals_bonds_flaws = self._load_json(self.data_path / "ideals_bonds_flaws.json")
        self.races = self._load_lore_files("races")
        print("World data loaded successfully.")

    def _load_json(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)

    def _load_lore_files(self, subfolder):
        lore_dict = {}
        folder_path = self.data_path / subfolder
        for file_path in folder_path.glob("*.json"):
            data = self._load_json(file_path)
            if 'entity' in data and 'name' in data['entity']: lore_dict[data['entity']['name']] = data
        return lore_dict

    def _weighted_choice(self, choices_dict):
        total_weight = sum(choices_dict.values())
        if total_weight == 0: return random.choice(list(choices_dict.keys()))
        choice_num = random.uniform(0, total_weight)
        current_weight = 0
        for choice, weight in choices_dict.items():
            current_weight += weight
            if choice_num <= current_weight: return choice
        return list(choices_dict.keys())[-1]

    def _generate_name(self, name_style, race):
        prompt = f"Generate a single, plausible, fantasy {race} name with a {name_style} cultural style. Provide only the name and nothing else."
        payload = {"model": LLM_MODEL_NAME, "prompt": prompt, "stream": False}
        try:
            response = requests.post(LLM_API_URL, json=payload, timeout=15)
            response.raise_for_status()
            response_json = response.json()
            return response_json.get('response', 'Nameus Fallbackus').strip()
        except requests.exceptions.RequestException:
            print(f"\n--- LLM Connection Error: Using fallback name. ---\n")
            return f"Fallback {race}"

    def generate_npc(self):
        npc = {}
        hometown_type = random.choice(list(self.rulebook.keys()))
        rules = self.rulebook[hometown_type]
        npc['hometown'] = random.choice(rules['village_names']) if hometown_type == "Countryside" else hometown_type
        npc['race'] = self._weighted_choice(rules['race_weights'])
        npc['class'] = self._weighted_choice(rules.get('class_archetype_weights', {"Adventurer": 1}))
        if npc['race'] == "Warforged": npc['organization'] = "Gladiators"
        elif npc['class'] == "Wizard" and npc['hometown'] == "Kashal": npc['organization'] = "Mages Guild"
        else: npc['organization'] = self._weighted_choice(rules['organization_weights'])
        npc['pantheon'] = self._weighted_choice(rules['pantheon_weights'])
        if npc['race'] == 'Tiefling': npc['social_class'] = "Outcast"
        elif npc['race'] == 'Warforged': npc['social_class'] = "Enslaved"
        else: npc['social_class'] = random.choice(rules.get('social_class_pool', ['Commoner']))
        npc['traits'] = [random.choice(self.personality_traits)['trait'] for _ in range(2)]
        npc['ideal'] = random.choice(self.ideals_bonds_flaws['ideals'])['text']
        npc['bond'] = random.choice(self.ideals_bonds_flaws['bonds'])['text']
        npc['flaw'] = random.choice(self.ideals_bonds_flaws['flaws'])['text']
        npc['name'] = self._generate_name(rules.get('name_style', 'common_anglo'), npc['race'])
        return npc

    def format_for_fvtt(self, npc_data):
        archetype = npc_data['class'].lower()
        stat_block_key = 'guard' if 'guard' in archetype else 'mage' if 'mage' in archetype or 'wizard' in archetype else 'commoner'
        stats = STAT_BLOCKS_5E[stat_block_key]
        biography = (
            f"<h1>{npc_data['name']}</h1><p><em>{npc_data['race']} {npc_data['class']} from {npc_data['hometown']}</em></p>"
            f"<p><strong>Faction:</strong> {npc_data['organization']}<br>"
            f"<strong>Ideal:</strong> {npc_data['ideal']}<br><strong>Bond:</strong> {npc_data['bond']}<br><strong>Flaw:</strong> {npc_data['flaw']}</p>"
        )
        return {"name": npc_data['name'],"type": "npc","img": "icons/svg/mystery-man.svg",
            "system": {"abilities": {key: {"value": val} for key, val in stats.items() if key in ['str', 'dex', 'con', 'int', 'wis', 'cha']},
                "attributes": {"ac": {"flat": stats['ac']}, "hp": {"value": stats['hp'], "max": stats['hp']}},
                "details": {"biography": {"value": biography}}}}

    def format_for_daggerheart(self, npc_data):
        """Assembles the final NPC data into the updated Daggerheart adversary format."""
        archetype = npc_data['class'].lower()
        stat_block_key = 'guard' if 'guard' in archetype else 'mage' if 'mage' in archetype or 'wizard' in archetype else 'noble' if 'noble' in npc_data.get('social_class', '').lower() else 'commoner'
        stats = DAGGERHEART_STATS[stat_block_key]
        
        # --- MODIFIED SECTION ---
        # Helper to correctly parse damage strings like "1d8+2"
        damage_string = stats['attack']['damage']
        damage_parts = damage_string.split('+')
        dice_part = damage_parts[0]
        damage_bonus = int(damage_parts[1]) if len(damage_parts) > 1 else 0
        
        # Extract *only* the die type (e.g., "d8" from "1d8") for the dice field
        # It assumes a single die, which is standard for basic adversary attacks.
        die_type = f"d{dice_part.split('d')[1]}"
        # --- END MODIFIED SECTION ---

        return {
            "name": npc_data['name'],"type": "adversary","img": "icons/svg/mystery-man.svg",
            "prototypeToken": {"name": npc_data['name'],"texture": {"src": "icons/svg/mystery-man.svg"},"width": 1, "height": 1, "disposition": -1,"bar1": {"attribute": "resources.hitPoints"},"bar2": {"attribute": "resources.stress"}},
            "system": {"difficulty": stats['difficulty'],"damageThresholds": stats['thresholds'],
                "resources": {"hitPoints": {"value": 0, "max": stats['hp'], "isReversed": True},"stress": {"value": 0, "max": stats['stress'], "isReversed": True}},
                "resistance": {"physical": {"resistance": False, "immunity": False, "reduction": 0},"magical": {"resistance": False, "immunity": False, "reduction": 0}},
                "type": stats['type'],"tier": stats['tier'],"hordeHp": 1,
                "experiences": {self._generate_id(16): {"name": stats['experience']['name'],"value": stats['experience']['value']}},
                "description": f"<p>A {npc_data['race']} {npc_data['class']} from {npc_data['hometown']}.</p>",
                "motivesAndTactics": npc_data['ideal'],
                "attack": {"name": stats['attack']['name'],"roll": {"bonus": stats['attack']['bonus']},
                    "damage": {"parts": [{"value": {
                        "dice": die_type, # Use the corrected die type here
                        "bonus": damage_bonus
                        },"applyTo": "hitPoints","type": ["physical"]}]},"img": "icons/svg/sword.svg"}},
            "items": []}

    def post_to_kanka(self, npc_data):
        # (This function remains unchanged)
        pass

if __name__ == "__main__":
    try:
        engine = NPCEngine(JSON_DIR)
        npc_data = engine.generate_npc()

        print("\n--- 1. NPC Summary (Terminal) ---")
        print(json.dumps(npc_data, indent=2))
        print("---------------------------------\n")

        print("--- 2. Saving Foundry VTT (D&D 5e) File ---")
        foundry_npc_5e = engine.format_for_fvtt(npc_data)
        fvtt_filename = f"{npc_data['name'].replace(' ', '_')}-fvtt.json"
        with open(fvtt_filename, 'w', encoding='utf-8') as f: json.dump(foundry_npc_5e, f, indent=4)
        print(f"Saved file as: {fvtt_filename}")
        print("-----------------------------------------\n")

        print("--- 3. Saving Foundry VTT (Daggerheart) File ---")
        foundry_npc_dh = engine.format_for_daggerheart(npc_data)
        dh_filename = f"{npc_data['name'].replace(' ', '_')}-dh.json"
        with open(dh_filename, 'w', encoding='utf-8') as f: json.dump(foundry_npc_dh, f, indent=4)
        print(f"Saved file as: {dh_filename}")
        print("----------------------------------------------\n")
        
        if POST_TO_KANKA:
            print("--- 4. Posting to Kanka.io ---")
            engine.post_to_kanka(npc_data)
            print("------------------------------\n")
        else:
            print("--- 4. Posting to Kanka.io (DISABLED) ---")
            print("To enable, change POST_TO_KANKA to True in the script.")
            print("-----------------------------------------\n")

    except Exception as e:
        print(f"A critical error occurred: {e}")