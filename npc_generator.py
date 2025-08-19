import json
import os
import re
import secrets
import requests
import random
import time
from pathlib import Path
from dotenv import load_dotenv

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

# --- CONFIGURATION ---
JSON_DIR = Path(__file__).parent / "json"
POST_TO_KANKA = True
KANKA_API_TOKEN = os.getenv("KANKA_API_TOKEN") 
CAMPAIGN_ID = os.getenv("CAMPAIGN_ID")
LLM_API_URL = "http://localhost:11434/api/generate"
LLM_MODEL_NAME = "phi3:mini"

# (Stat blocks remain the same)
STAT_BLOCKS_5E = {
    "commoner": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10, "hp": 4, "ac": 10},
    "guard": {"str": 13, "dex": 12, "con": 12, "int": 10, "wis": 11, "cha": 10, "hp": 11, "ac": 16},
    "mage": {"str": 9, "dex": 14, "con": 11, "int": 16, "wis": 12, "cha": 11, "hp": 9, "ac": 12},
}
DAGGERHEART_STATS = {
    "commoner": {"difficulty": 10, "hp": 2, "stress": 3, "type": "social", "tier": 1, "thresholds": {"major": 3, "severe": 6}, "attack": {"name": "Unarmed", "bonus": 0, "damage": "1d4"}, "experience": {"name": "Local Lore", "value": 2}},
    "guard": {"difficulty": 13, "hp": 4, "stress": 4, "type": "physical", "tier": 1, "thresholds": {"major": 4, "severe": 8}, "attack": {"name": "Sword", "bonus": 2, "damage": "1d8+2"}, "experience": {"name": "Soldiering", "value": 3}},
    "mage": {"difficulty": 14, "hp": 3, "stress": 5, "type": "magical", "tier": 1, "thresholds": {"major": 4, "severe": 8}, "attack": {"name": "Magic Bolt", "bonus": 3, "damage": "1d10"}, "experience": {"name": "Arcana", "value": 4}},
    "noble": {"difficulty": 12, "hp": 3, "stress": 4, "type": "social", "tier": 1, "thresholds": {"major": 4, "severe": 8}, "attack": {"name": "Dagger", "bonus": 1, "damage": "1d6+1"}, "experience": {"name": "Etiquette", "value": 3}}
}


class NPCEngine:
    def __init__(self, data_path):
        self.data_path = data_path
        self.load_all_data()

    # (..._generate_id, load_all_data, _load_json, _load_lore_files, _weighted_choice are unchanged...)
    def _generate_id(self, length=16):
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
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(LLM_API_URL, json=payload, timeout=15)
                response.raise_for_status()
                response_json = response.json()
                return response_json.get('response', 'Nameus Fallbackus').strip()
            except requests.exceptions.RequestException:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"\n--- LLM Connection Error: Using fallback name. ---\n")
                    return f"Fallback {race}"

    # --- NEW FUNCTION ---
    def _generate_backstory(self, npc_data):
        """Generates a one-paragraph backstory by calling a local LLM API."""
        print("Generating backstory from LLM...")
        
        # --- MODIFIED: Added a stronger concluding instruction ---
        prompt = (
            "Write a single, compelling backstory paragraph (around 50-70 words) for a new tabletop RPG character. "
            "Weave the following details together logically:\n"
            f"- Name: {npc_data['name']}\n"
            f"- Race: {npc_data['race']}\n"
            f"- Class/Archetype: {npc_data['class']}\n"
            f"- Hometown: {npc_data['hometown']}\n"
            f"- Organization: {npc_data['organization']}\n"
            f"- Core Personality: {npc_data['traits'][0]}, {npc_data['traits'][1]}\n"
            f"- Ideal: {npc_data['ideal']}\n"
            f"- Bond: {npc_data['bond']}\n"
            f"- Flaw: {npc_data['flaw']}\n\n"
            "Provide ONLY the single paragraph backstory and nothing else."
        )
        
        payload = {
            "model": LLM_MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "stop": ["---", "\n\n\n"] # --- NEW: Tell the model to stop if it generates these
            }
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(LLM_API_URL, json=payload, timeout=30)
                response.raise_for_status()
                response_json = response.json()
                
                backstory_text = response_json.get('response', 'No backstory could be generated.').strip()
                
                # --- NEW: Manually clean the output as a final safety measure ---
                cleaned_backstory = backstory_text.split('---')[0].strip()
                
                return cleaned_backstory

            except requests.exceptions.RequestException:
                if attempt < max_retries - 1:
                    print(f"LLM backstory attempt {attempt + 1} of {max_retries} failed. Retrying...")
                    time.sleep(1)
                else:
                    print(f"\n--- LLM Connection Error: Could not generate backstory. ---\n")
                    return "No backstory could be generated."

    def generate_npc(self):
        npc = {}
        # (Generation of core attributes is the same)
        hometown_type = random.choice(list(self.rulebook.keys()))
        rules = self.rulebook[hometown_type]
        npc['hometown'] = random.choice(rules['village_names']) if hometown_type == "Countryside" else hometown_type
        npc['race'] = self._weighted_choice(rules['race_weights'])
        npc['class'] = self._weighted_choice(rules.get('class_archetype_weights', {"Adventurer": 1}))
        if npc['race'] == "Warforged": npc['organization'] = "Gladiators"
        else: npc['organization'] = self._weighted_choice(rules['organization_weights'])
        npc['pantheon'] = self._weighted_choice(rules['pantheon_weights'])
        if npc['race'] == 'Invernis': npc['social_class'] = "Outcast"
        else: npc['social_class'] = random.choice(rules.get('social_class_pool', ['Commoner']))
        npc['traits'] = [random.choice(self.personality_traits)['trait'] for _ in range(2)]
        npc['ideal'] = random.choice(self.ideals_bonds_flaws['ideals'])['text']
        npc['bond'] = random.choice(self.ideals_bonds_flaws['bonds'])['text']
        npc['flaw'] = random.choice(self.ideals_bonds_flaws['flaws'])['text']
        npc['name'] = self._generate_name(rules.get('name_style', 'common_anglo'), npc['race'])
        
        # --- MODIFIED: Call the new backstory function ---
        npc['backstory'] = self._generate_backstory(npc)
        
        return npc

    def format_for_fvtt(self, npc_data):
        # (This function is updated to include the backstory)
        archetype = npc_data['class'].lower()
        stat_block_key = 'guard' if 'guard' in archetype else 'mage' if 'mage' in archetype else 'commoner'
        stats = STAT_BLOCKS_5E[stat_block_key]
        biography = (
            f"<h1>{npc_data['name']}</h1><p><em>{npc_data['race']} {npc_data['class']} from {npc_data['hometown']}</em></p>"
            f"<h2>Backstory</h2><p>{npc_data['backstory']}</p><hr>"
            f"<p><strong>Faction:</strong> {npc_data['organization']}<br>"
            f"<strong>Ideal:</strong> {npc_data['ideal']}<br><strong>Bond:</strong> {npc_data['bond']}<br><strong>Flaw:</strong> {npc_data['flaw']}</p>"
        )
        # (Rest of the function is the same)
        return {"name": npc_data['name'],"type": "npc","img": "icons/svg/mystery-man.svg",
            "system": {"abilities": {key: {"value": val} for key, val in stats.items() if key in ['str', 'dex', 'con', 'int', 'wis', 'cha']},
                "attributes": {"ac": {"flat": stats['ac']}, "hp": {"value": stats['hp'], "max": stats['hp']}},
                "details": {"biography": {"value": biography}}}}

    def format_for_daggerheart(self, npc_data):
        # (This function is updated to include the backstory)
        archetype = npc_data['class'].lower()
        stat_block_key = 'guard' if 'guard' in archetype else 'mage' if 'mage' in archetype else 'noble' if 'noble' in npc_data.get('social_class', '').lower() else 'commoner'
        stats = DAGGERHEART_STATS[stat_block_key]
        damage_dice, damage_bonus = (stats['attack']['damage'].split('+') + ['0'])[:2]
        die_type = f"d{damage_dice.split('d')[1]}"
        description = f"<p>A {npc_data['race']} {npc_data['class']} from {npc_data['hometown']}.</p><h2>Backstory</h2><p>{npc_data['backstory']}</p>"
        # (Rest of the function is the same)
        return {
            "name": npc_data['name'],"type": "adversary","img": "icons/svg/mystery-man.svg",
            "prototypeToken": {"name": npc_data['name'],"texture": {"src": "icons/svg/mystery-man.svg"},"width": 1, "height": 1, "disposition": -1,"bar1": {"attribute": "resources.hitPoints"},"bar2": {"attribute": "resources.stress"}},
            "system": {"difficulty": stats['difficulty'],"damageThresholds": stats['thresholds'],
                "resources": {"hitPoints": {"value": 0, "max": stats['hp'], "isReversed": True},"stress": {"value": 0, "max": stats['stress'], "isReversed": True}},
                "resistance": {"physical": {"resistance": False, "immunity": False, "reduction": 0},"magical": {"resistance": False, "immunity": False, "reduction": 0}},
                "type": stats['type'],"tier": stats['tier'],"hordeHp": 1,
                "experiences": {self._generate_id(16): {"name": stats['experience']['name'],"value": stats['experience']['value']}},
                "description": description, "motivesAndTactics": npc_data['ideal'],
                "attack": {"name": stats['attack']['name'],"roll": {"bonus": stats['attack']['bonus']},
                    "damage": {"parts": [{"value": {"dice": die_type,"bonus": int(damage_bonus)},"applyTo": "hitPoints","type": ["physical"]}]},"img": "icons/svg/sword.svg"}},
            "items": []}

    def post_to_kanka(self, npc_data):
        """Formats and sends the generated NPC data to the Kanka API."""
        if not all([KANKA_API_TOKEN, CAMPAIGN_ID]):
            print("Kanka API Token or Campaign ID not found in .env file. Skipping post.")
            return
        
        entry_html = (
            f"<h2>Backstory</h2><p>{npc_data['backstory']}</p><hr>"
            f"<p><strong>Ideal:</strong> {npc_data['ideal']}</p><p><strong>Bond:</strong> {npc_data['bond']}</p><p><strong>Flaw:</strong> {npc_data['flaw']}</p>"
        )
        
        payload = {
            "name": npc_data['name'],
            "entry": entry_html,
            "title": f"{npc_data['race']} {npc_data['class']}",
            "is_private": True, # <-- Changed from False to True
            "race_id": self.kanka_ids['races'].get(npc_data['race']),
            "location_id": self.kanka_ids['locations'].get(npc_data['hometown']),
            "organisation_id": self.kanka_ids['organizations'].get(npc_data['organization'])
        }

        url = f"https://api.kanka.io/1.0/campaigns/{CAMPAIGN_ID}/characters"
        headers = {"Authorization": f"Bearer {KANKA_API_TOKEN}", "Content-Type": "application/json"}
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            created_char = response.json().get('data', {})
            print(f"Successfully created Kanka character: {created_char.get('name')} ({created_char.get('url')})")
        except requests.exceptions.HTTPError as e:
            print(f"Kanka Error: Could not create character. Status: {e.response.status_code}")

if __name__ == "__main__":
    # (The main execution block remains unchanged)
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