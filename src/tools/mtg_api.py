from typing import List, Optional, Dict, Any, Tuple
import httpx
from pydantic import BaseModel
from src.config import settings
from src.observability.tracing import tracing

class CardItem(BaseModel):
    name: str
    mana_cost: Optional[str] = ""
    cmc: Optional[float] = 0.0
    type_line: Optional[str] = ""
    oracle_text: Optional[str] = ""
    image_url: Optional[str] = ""
    rarity: Optional[str] = ""
    set_name: Optional[str] = ""


KNOWN_CANONICAL_CARDS: Dict[str, CardItem] = {
    "battlefield raptor": CardItem(
        name="Battlefield Raptor",
        mana_cost="{W}",
        cmc=1.0,
        type_line="Creature — Bird",
        oracle_text="Flying, first strike",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=503611&type=card"
    ),
    "rapaz del campo de batalla": CardItem(
        name="Battlefield Raptor",
        mana_cost="{W}",
        cmc=1.0,
        type_line="Creature — Bird",
        oracle_text="Flying, first strike",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=503611&type=card"
    ),
    "ninja of the deep hours": CardItem(
        name="Ninja of the Deep Hours",
        mana_cost="{3}{U}",
        cmc=4.0,
        type_line="Creature — Human Ninja",
        oracle_text="Ninjutsu {1}{U} ({1}{U}, Return an unblocked attacker you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever Ninja of the Deep Hours deals combat damage to a player, you may draw a card.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=451036&type=card"
    ),
    "ninja de horas tardías": CardItem(
        name="Ninja of the Deep Hours",
        mana_cost="{3}{U}",
        cmc=4.0,
        type_line="Creature — Human Ninja",
        oracle_text="Ninjutsu {1}{U} ({1}{U}, Return an unblocked attacker you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever Ninja of the Deep Hours deals combat damage to a player, you may draw a card.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=451036&type=card"
    ),
    "ninja de horas tardias": CardItem(
        name="Ninja of the Deep Hours",
        mana_cost="{3}{U}",
        cmc=4.0,
        type_line="Creature — Human Ninja",
        oracle_text="Ninjutsu {1}{U} ({1}{U}, Return an unblocked attacker you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever Ninja of the Deep Hours deals combat damage to a player, you may draw a card.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=451036&type=card"
    ),
    "lightning bolt": CardItem(
        name="Lightning Bolt",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=442130&type=card"
    ),
    "rayo": CardItem(
        name="Lightning Bolt",
        mana_cost="{R}",
        cmc=1.0,
        type_line="Instant",
        oracle_text="Lightning Bolt deals 3 damage to any target.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=442130&type=card"
    ),
    "black lotus": CardItem(
        name="Black Lotus",
        mana_cost="{0}",
        cmc=0.0,
        type_line="Artifact",
        oracle_text="{T}, Sacrifice Black Lotus: Add three mana of any one color.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=382866&type=card"
    ),
    "loto negro": CardItem(
        name="Black Lotus",
        mana_cost="{0}",
        cmc=0.0,
        type_line="Artifact",
        oracle_text="{T}, Sacrifice Black Lotus: Add three mana of any one color.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=382866&type=card"
    ),
    "sheoldred, the apocalypse": CardItem(
        name="Sheoldred, the Apocalypse",
        mana_cost="{2}{B}{B}",
        cmc=4.0,
        type_line="Legendary Creature — Phyrexian Praetor",
        oracle_text="Deathtouch\nWhenever you draw a card, you gain 2 life.\nWhenever an opponent draws a card, they lose 2 life.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=574587&type=card"
    ),
    "sheoldred": CardItem(
        name="Sheoldred, the Apocalypse",
        mana_cost="{2}{B}{B}",
        cmc=4.0,
        type_line="Legendary Creature — Phyrexian Praetor",
        oracle_text="Deathtouch\nWhenever you draw a card, you gain 2 life.\nWhenever an opponent draws a card, they lose 2 life.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=574587&type=card"
    ),
    "notion thief": CardItem(
        name="Notion Thief",
        mana_cost="{2}{U}{B}",
        cmc=4.0,
        type_line="Creature — Human Rogue",
        oracle_text="Flash\nIf an opponent would draw a card except the first one they draw in each of their draw steps, instead that player skips that draw and you draw a card.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=497746&type=card"
    ),
    "ladrón de nociones": CardItem(
        name="Notion Thief",
        mana_cost="{2}{U}{B}",
        cmc=4.0,
        type_line="Creature — Human Rogue",
        oracle_text="Flash\nIf an opponent would draw a card except the first one they draw in each of their draw steps, instead that player skips that draw and you draw a card.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=497746&type=card"
    ),
    "ladron de nociones": CardItem(
        name="Notion Thief",
        mana_cost="{2}{U}{B}",
        cmc=4.0,
        type_line="Creature — Human Rogue",
        oracle_text="Flash\nIf an opponent would draw a card except the first one they draw in each of their draw steps, instead that player skips that draw and you draw a card.",
        image_url="https://gatherer.wizards.com/Handlers/Image.ashx?multiverseid=497746&type=card"
    )
}


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
        - color: canonical 'W', 'U', 'B', 'R', 'G' (or localized name)
        - subtype: canonical 'Warrior', 'Ninja', etc.
        - card_type: e.g. 'Creature', 'Instant'
        - cmc: exact converted mana cost (e.g. 1)
        - max_cmc: maximum converted mana cost (e.g. 1 means <= 1)
        """
        # 1. Build Query Parameters
        params: Dict[str, Any] = {"pageSize": max(limit * 3, 20)}
        
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
            mapped_color = color_map.get(color.lower().strip(), color.upper())
            params["colorIdentity"] = mapped_color

        subtype_map = {
            "guerrero": "Warrior", "warrior": "Warrior",
            "ninja": "Ninja",
            "soldado": "Soldier", "soldier": "Soldier",
            "caballero": "Knight", "knight": "Knight",
            "mago": "Wizard", "wizard": "Wizard",
            "clerigo": "Cleric", "clérigo": "Cleric", "cleric": "Cleric",
            "picaro": "Rogue", "pícaro": "Rogue", "rogue": "Rogue",
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

        # BUG FIX (SPEC 10):
        # Only set exact cmc in API params if exact cmc is requested.
        # If max_cmc is set, do NOT set params["cmc"] = str(max_cmc), because
        # that would filter cmc == max_cmc on the API and miss cmc=0 cards.
        # Instead, fetch candidates and filter locally with card_cmc <= max_cmc.
        if cmc is not None:
            params["cmc"] = str(cmc)

        cache_key = f"{params}_{max_cmc}_{limit}"
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

        # 3. Parse and Deduplicate by Card Name with local <= max_cmc enforcement
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

    def get_card(self, name: str) -> Optional[CardItem]:
        """
        Retrieves full Oracle card data by name.
        Uses in-memory cache and canonical seed dictionary first, then queries the official API.
        Returns None if card does not exist.
        """
        with tracing.observation(
            name="mtg_api_get_card",
            as_type="tool",
            input={"name": name}
        ) as tool_obs:
            card = self._get_card_impl(name)
            tool_obs.update(output={
                "found": card is not None,
                "card_name": card.name if card else None
            })
            return card

    def _get_card_impl(self, name: str) -> Optional[CardItem]:
        clean_name = name.strip().lower()
        if not clean_name:
            return None

        # 1. Check known canonical seed cards (guaranteed instant & offline)
        if clean_name in KNOWN_CANONICAL_CARDS:
            return KNOWN_CANONICAL_CARDS[clean_name]

        # 2. Check internal cache
        cache_key = f"get_card_{clean_name}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return cached[0] if cached else None

        # 3. Query MTG API
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{self.base_url}/cards",
                    params={"name": name, "pageSize": 5},
                    headers=self.headers
                )
                if response.status_code == 200:
                    data = response.json()
                    cards = data.get("cards", [])
                    if cards:
                        # Prefer exact case-insensitive match if available
                        matched = next(
                            (c for c in cards if c.get("name", "").lower() == clean_name),
                            cards[0]
                        )
                        item = CardItem(
                            name=matched.get("name", ""),
                            mana_cost=matched.get("manaCost", ""),
                            cmc=float(matched.get("cmc", 0.0)),
                            type_line=matched.get("type", ""),
                            oracle_text=matched.get("text", ""),
                            image_url=matched.get("imageUrl", ""),
                            rarity=matched.get("rarity", ""),
                            set_name=matched.get("setName", "")
                        )
                        self._cache[cache_key] = [item]
                        return item
        except Exception:
            pass

        # Mark as not found in cache so we don't repeat failed requests
        self._cache[cache_key] = []
        return None

    def resolve_cards(self, names: List[str]) -> Tuple[List[CardItem], List[str]]:
        """
        Resolves a list of candidate card names into CardItem objects.
        Returns:
            Tuple[List[CardItem], List[str]]: (found_cards, missing_names)
        """
        resolved: List[CardItem] = []
        missing: List[str] = []
        seen = set()

        for raw_name in names:
            name = raw_name.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            card = self.get_card(name)
            if card:
                resolved.append(card)
            else:
                missing.append(name)

        return resolved, missing

