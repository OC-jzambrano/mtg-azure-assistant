from typing import List, Optional, Dict, Any
import httpx
from pydantic import BaseModel
from src.config import settings

class CardItem(BaseModel):
    name: str
    mana_cost: Optional[str] = ""
    cmc: Optional[float] = 0.0
    type_line: Optional[str] = ""
    oracle_text: Optional[str] = ""
    image_url: Optional[str] = ""
    rarity: Optional[str] = ""
    set_name: Optional[str] = ""

class MTGCardSearchTool:
    """Tool that queries the official MTG API (magicthegathering.io) with structured parameters."""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.mtg_api_base_url
        self.headers = {
            "User-Agent": settings.mtg_user_agent,
            "Accept": "application/json"
        }
        self._cache: Dict[str, List[CardItem]] = {}

    def search_cards(
        self,
        name: Optional[str] = None,
        color: Optional[str] = None,
        subtype: Optional[str] = None,
        card_type: Optional[str] = None,
        cmc: Optional[int] = None,
        max_cmc: Optional[int] = None,
        limit: int = 5
    ) -> List[CardItem]:
        """
        Searches cards with structured filters:
        - name: e.g. 'Battlefield Raptor'
        - color: e.g. 'White', 'Red', 'Blue', 'Black', 'Green'
        - subtype: e.g. 'Warrior', 'Ninja', 'Dragon'
        - card_type: e.g. 'Creature', 'Instant'
        - cmc: exact converted mana cost (e.g. 1)
        - max_cmc: maximum converted mana cost (e.g. 1 means < 2)
        """
        # 1. Build Query Parameters
        params: Dict[str, Any] = {"pageSize": max(limit, 10)}
        
        if name:
            params["name"] = name
            
        color_map = {
            "blanco": "W", "white": "W", "w": "W",
            "azul": "U", "blue": "U", "u": "U",
            "negro": "B", "black": "B", "b": "B",
            "rojo": "R", "red": "R", "r": "R",
            "verde": "G", "green": "G", "g": "G"
        }
        if color:
            mapped_color = color_map.get(color.lower().strip(), color)
            params["colorIdentity"] = mapped_color

        subtype_map = {
            "guerrero": "Warrior", "warrior": "Warrior",
            "ninja": "Ninja",
            "soldado": "Soldier", "soldier": "Soldier",
            "caballero": "Knight", "knight": "Knight",
            "mago": "Wizard", "wizard": "Wizard",
            "clerigo": "Cleric", "cleric": "Cleric",
            "picaro": "Rogue", "rogue": "Rogue",
            "dragon": "Dragon", "dragón": "Dragon",
            "angel": "Angel", "ángel": "Angel",
            "ave": "Bird", "bird": "Bird",
            "zombie": "Zombie", "elfo": "Elf", "elf": "Elf"
        }
        if subtype:
            mapped_subtype = subtype_map.get(subtype.lower().strip(), subtype.capitalize())
            params["subtypes"] = mapped_subtype

        type_map = {
            "criatura": "Creature", "creature": "Creature",
            "instantaneo": "Instant", "instantáneo": "Instant", "instant": "Instant",
            "conjuro": "Sorcery", "sorcery": "Sorcery",
            "encantamiento": "Enchantment", "enchantment": "Enchantment",
            "artefacto": "Artifact", "artifact": "Artifact",
            "tierra": "Land", "land": "Land",
            "planeswalker": "Planeswalker"
        }
        if card_type:
            mapped_type = type_map.get(card_type.lower().strip(), card_type.capitalize())
            params["types"] = mapped_type

        # Handle CMC (under 2 means cmc=0 or cmc=1)
        if cmc is not None:
            params["cmc"] = str(cmc)
        elif max_cmc is not None:
            params["cmc"] = str(max_cmc)

        cache_key = f"{params}"
        if cache_key in self._cache:
            return self._cache[cache_key][:limit]

        # 2. Execute Request
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{self.base_url}/cards",
                    params=params,
                    headers=self.headers
                )
                if response.status_code != 200:
                    return []
                
                data = response.json()
                raw_cards = data.get("cards", [])
        except Exception:
            return []

        # 3. Parse and Deduplicate by Card Name
        results: List[CardItem] = []
        seen_names = set()

        for c in raw_cards:
            card_name = c.get("name", "")
            if not card_name or card_name in seen_names:
                continue

            card_cmc = float(c.get("cmc", 0.0))
            if max_cmc is not None and card_cmc > max_cmc:
                continue

            item = CardItem(
                name=card_name,
                mana_cost=c.get("manaCost", ""),
                cmc=card_cmc,
                type_line=c.get("type", ""),
                oracle_text=c.get("text", ""),
                image_url=c.get("imageUrl", ""),
                rarity=c.get("rarity", ""),
                set_name=c.get("setName", "")
            )
            results.append(item)
            seen_names.add(card_name)
            if len(results) >= limit:
                break

        self._cache[cache_key] = results
        return results
