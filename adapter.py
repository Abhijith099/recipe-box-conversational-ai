"""
adapter.py - Evidence-Based Recipe Adapter (Task 3)
Finds substitutes using culinary roles, gathers local SQLite evidence (citing Recipe IDs),
and rewrites ingredient lists and instructions with predicted trade-offs.
"""

import re
import json
from typing import Dict, Any, List, Optional
from engine import get_db

# 1. Simple culinary dictionary: Role, Candidates, Ratio, Trade-offs
SUBSTITUTION_RULES = {
    "egg": {
        "role": "Binding, moisture, and leavening structure",
        "substitutes": [
            {
                "name": "applesauce",
                "ratio": "1/4 cup unsweetened applesauce per egg",
                "restriction_safe": ["dairy-free", "vegan", "nut-free"],
                "trade_off": "Adds moisture and mild sweetness; crumb will be denser and slightly less airy."
            },
            {
                "name": "mashed banana",
                "ratio": "1/4 cup mashed ripe banana per egg",
                "restriction_safe": ["dairy-free", "vegan", "nut-free"],
                "trade_off": "Provides strong binding and moisture; adds noticeable banana flavor."
            },
            {
                "name": "ground flaxseed with water",
                "ratio": "1 tbsp ground flaxseed mixed with 3 tbsp warm water per egg",
                "restriction_safe": ["dairy-free", "vegan", "nut-free"],
                "trade_off": "Good binding power; imparts a slight nutty flavor and tiny brown flecks."
            }
        ]
    },
    "cream": {
        "role": "Richness, fat content, and sauce thickening",
        "substitutes": [
            {
                "name": "coconut milk",
                "ratio": "1:1 ratio with heavy cream (use full-fat canned coconut milk)",
                "restriction_safe": ["dairy-free", "vegan", "lactose-free"],
                "trade_off": "Similar viscosity and richness; leaves a subtle coconut aroma that pairs well with spices."
            },
            {
                "name": "olive oil and pasta water",
                "ratio": "2 tbsp olive oil emulsified with starchy pasta water",
                "restriction_safe": ["dairy-free", "vegan", "nut-free", "lactose-free"],
                "trade_off": "Lighter mouthfeel, glossy coating, less creamy richness but enhanced savory flavor."
            },
            {
                "name": "cashew cream",
                "ratio": "1:1 ratio (soaked raw cashews blended with water)",
                "restriction_safe": ["dairy-free", "vegan", "lactose-free"],
                "trade_off": "Very close neutral creamy texture; requires a high-speed blender, not nut-allergy safe."
            }
        ]
    },
    "milk": {
        "role": "Liquid base, moisture, and dissolved sugars",
        "substitutes": [
            {
                "name": "almond milk",
                "ratio": "1:1 ratio with dairy milk",
                "restriction_safe": ["dairy-free", "vegan", "lactose-free"],
                "trade_off": "Slightly thinner body; neutral taste in savory dishes if unsweetened."
            },
            {
                "name": "oat milk",
                "ratio": "1:1 ratio with dairy milk",
                "restriction_safe": ["dairy-free", "vegan", "nut-free", "lactose-free"],
                "trade_off": "Creamy consistency, mild oat sweetness, browns well in baking."
            }
        ]
    },
    "butter": {
        "role": "Fat, flakiness, flavor, and moisture",
        "substitutes": [
            {
                "name": "olive oil",
                "ratio": "3/4 cup olive oil for every 1 cup butter",
                "restriction_safe": ["dairy-free", "vegan", "nut-free"],
                "trade_off": "Tender texture; cannot be creamed with sugar for fluffy cakes, distinct fruity aroma."
            },
            {
                "name": "coconut oil",
                "ratio": "1:1 ratio (solidified for baking)",
                "restriction_safe": ["dairy-free", "vegan", "nut-free"],
                "trade_off": "Behaves like solid fat at room temperature; gives slight crispness to cookies."
            }
        ]
    }
}


class RecipeAdapter:
    def __init__(self):
        pass

    def find_local_evidence(self, dish_type: str, substitute_name: str, target_to_exclude: str, limit: int = 3) -> Dict[str, Any]:
        """
        Searches the local SQLite database for recipes of the same dish type
        that use the substitute WITHOUT using the excluded ingredient.
        Returns the recipe IDs as grounded evidence, along with evidence strength (direct vs indirect).
        """
        sub_keyword = substitute_name.split()[0].lower()
        dish_keyword = dish_type.split()[0].lower() if dish_type else ""
        evidence_level = "inadequate"

        with get_db() as conn:
            cur = conn.cursor()
            # If dish_keyword exists, search for dish_type + substitute
            rows = []
            if dish_keyword and len(dish_keyword) > 2:
                query = """
                    SELECT id, title, ingredients_json, step_count 
                    FROM recipes 
                    WHERE title LIKE ? AND ingredients_json LIKE ? AND ingredients_json NOT LIKE ?
                    LIMIT ?
                """
                cur.execute(query, [f"%{dish_keyword}%", f"%{sub_keyword}%", f"%{target_to_exclude}%", limit])
                rows = cur.fetchall()
                if rows:
                    evidence_level = "direct"

            # Fallback: search across all recipes if no exact dish-title match
            if not rows:
                query = """
                    SELECT id, title, ingredients_json, step_count 
                    FROM recipes 
                    WHERE ingredients_json LIKE ? AND ingredients_json NOT LIKE ?
                    LIMIT ?
                """
                cur.execute(query, [f"%{sub_keyword}%", f"%{target_to_exclude}%", limit])
                rows = cur.fetchall()
                if rows:
                    evidence_level = "indirect"

        evidence_items = []
        for r in rows:
            evidence_items.append({
                "id": r["id"],
                "title": r["title"],
                "steps": r["step_count"]
            })
            
        return {
            "level": evidence_level,
            "items": evidence_items
        }

    def adapt(self, base_recipe: Dict[str, Any], target_ingredient: str, restriction: Optional[str] = None) -> Dict[str, Any]:
        """
        Adapts a given recipe by replacing target_ingredient according to culinary rules,
        cites local database evidence, and rewrites both ingredients and instructions.
        """
        target = target_ingredient.lower().strip()
        # Normalize target to singular
        if target.endswith("s") and not target.endswith("ss"):
            target_singular = target[:-1]
        else:
            target_singular = target

        rule_key = None
        for key in SUBSTITUTION_RULES:
            if key in target_singular or target_singular in key:
                rule_key = key
                break

        if not rule_key:
            return {
                "success": False,
                "message": f"No grounded substitution rule found for '{target_ingredient}'. To prevent ungrounded advice, only verified culinary roles are supported."
            }

        rule = SUBSTITUTION_RULES[rule_key]
        substitutes = rule["substitutes"]

        # Filter by restriction if specified (e.g. dairy-free, nut-free)
        selected_sub = None
        if restriction:
            restr_clean = restriction.lower()
            for cand in substitutes:
                if any(r in restr_clean for r in cand["restriction_safe"]):
                    selected_sub = cand
                    break
        if not selected_sub:
            selected_sub = substitutes[0]

        # 1. Fetch local database evidence (Cite Recipe IDs)
        dish_name = base_recipe.get("title", "")
        evidence_res = self.find_local_evidence(dish_name, selected_sub["name"], rule_key)
        evidence = evidence_res["items"]
        evidence_level = evidence_res["level"]

        # 2. Rewrite Ingredients
        original_ingredients = base_recipe.get("ingredients", [])
        updated_ingredients = []
        replaced = False

        for ing in original_ingredients:
            if re.search(r'\b' + re.escape(rule_key), ing, flags=re.IGNORECASE):
                updated_ingredients.append(f"{selected_sub['ratio']} (Substituted for: {ing})")
                replaced = True
            else:
                updated_ingredients.append(ing)

        if not replaced:
            updated_ingredients.append(f"Add {selected_sub['ratio']} (Replacing {target_ingredient})")

        # 3. Rewrite Instructions
        raw_instructions = base_recipe.get("instructions", "")
        pattern = re.compile(r'\b' + re.escape(rule_key) + r'(?:s)?\b', flags=re.IGNORECASE)
        revised_instructions = pattern.sub(selected_sub["name"], raw_instructions)

        return {
            "success": True,
            "original_title": base_recipe.get("title", "Unknown Recipe"),
            "recipe_id": base_recipe.get("id", "N/A"),
            "target_ingredient": target_ingredient,
            "culinary_role": rule["role"],
            "chosen_substitute": selected_sub["name"],
            "ratio_guideline": selected_sub["ratio"],
            "local_evidence": evidence,
            "evidence_level": evidence_level,
            "trade_offs": selected_sub["trade_off"],
            "updated_ingredients": updated_ingredients,
            "revised_instructions": revised_instructions,
            "safety_disclaimer": "⚠️ Allergen Notice: Always verify packaged substitute labels. Recipe title matching in the dataset does not constitute certified clinical or medical allergen safety."
        }
