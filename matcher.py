"""
Task 2: Ingredient-Based Recipe Matching Engine.
Given a list of available ingredients and constraints/preferences:
- Retrieves and ranks candidate recipes from the 124,595-recipe dataset.
- Evaluates hard constraints strictly (e.g. excluded ingredients, max steps).
- Computes exact matched ingredients, missing/additional ingredients, and step counts.
- Uses an explainable, deterministic scoring approach.
- Clearly states when quantity sufficiency cannot be verified.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from engine import get_db, RESTRICTION_KEYWORDS

# Common pantry staples that shouldn't heavily penalize a recipe if missing
PANTRY_STAPLES = {
    "water", "salt", "black pepper", "pepper", "olive oil", "vegetable oil",
    "oil", "butter", "cooking spray", "sugar"
}

# Ingredient normalization map for standard plurals / variations
SYNONYMS = {
    "egg": "eggs",
    "onion": "onions",
    "tomato": "tomatoes",
    "potato": "potatoes",
    "clove garlic": "garlic",
    "garlic clove": "garlic",
    "scallion": "green onions",
    "scallions": "green onions",
    "bell pepper": "peppers",
}

def normalize_ingredient_token(name: str) -> str:
    """Normalizes an ingredient name for flexible matching while preserving distinct products."""
    name = name.lower().strip()
    # Strip leading quantities or measurements if passed (e.g. '2 eggs' -> 'eggs', '1 cup rice' -> 'rice')
    name = re.sub(r'^\d+[\s\/\d\.]*\s*(?:cups?|tbsp|tablespoons?|tsp|teaspoons?|oz|ounces?|lbs?|pounds?|cans?|cloves?|slices?|pieces?|pinch)?\s*(?:of\s+)?', '', name)
    name = name.strip()
    if name in SYNONYMS:
        name = SYNONYMS[name]
    # Simple plural normalization
    if name.endswith("es") and len(name) > 4:
        singular = name[:-2]
        if singular in ["tomato", "potato"]:
            return singular
    elif name.endswith("s") and not name.endswith("ss") and len(name) > 3:
        return name[:-1]
    return name

def clean_recipe_ingredient_item(raw_item: str) -> str:
    """Strips measurements and descriptors to extract the core ingredient item."""
    item = raw_item.lower()
    # Remove contents inside parentheses e.g. (10.5 ounce)
    item = re.sub(r'\(.*?\)', '', item)
    # Remove numbers, fractions
    item = re.sub(r'[\d\/\.\-]+', ' ', item)
    # Remove common units
    item = re.sub(r'\b(?:cups?|tbsp|tablespoons?|tsp|teaspoons?|oz|ounces?|pounds?|lbs?|cans?|cloves?|slices?|packages?|pinch|dash|bunch|stalks?)\b', ' ', item)
    # Remove prep descriptors
    item = re.sub(r'\b(?:diced|chopped|minced|sliced|peeled|shredded|grated|melted|cooked|crushed|fresh|freshly|ground|frozen|canned|divided|optional|to taste)\b', ' ', item)
    item = re.sub(r'\s+', ' ', item).strip()
    return item

class RecipeMatcher:
    def __init__(self):
        pass

    def match_recipes(
        self,
        user_ingredients: List[str],
        hard_exclusions: Optional[List[str]] = None,
        max_steps: Optional[int] = None,
        prefer_fewest_missing: bool = True,
        prefer_fewer_steps: bool = False,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Ranks recipes from the dataset based on available user ingredients and constraints.
        Returns detailed scoring breakdown, matched/missing ingredients, and explanations.
        """
        hard_exclusions = hard_exclusions or []
        
        # Check if quantities were provided by user
        has_quantities = any(re.search(r'\d', ing) for ing in user_ingredients)

        # Normalize user ingredient names
        norm_user_ing_map = {}
        for raw in user_ingredients:
            norm = normalize_ingredient_token(raw)
            if norm:
                norm_user_ing_map[norm] = raw

        # Expand hard exclusions into exclusion keywords
        expanded_exclusions = set()
        for exc in hard_exclusions:
            exc_clean = exc.lower().strip()
            if exc_clean in RESTRICTION_KEYWORDS:
                expanded_exclusions.update(RESTRICTION_KEYWORDS[exc_clean])
            else:
                expanded_exclusions.add(exc_clean)
                norm_exc = normalize_ingredient_token(exc_clean)
                expanded_exclusions.add(norm_exc)
                if norm_exc.endswith("s"):
                    expanded_exclusions.add(norm_exc[:-1])
                else:
                    expanded_exclusions.add(norm_exc + "s")

        # Filter out any user ingredients that are now in hard_exclusions
        active_norm_user_ing_map = {}
        for norm, raw in norm_user_ing_map.items():
            if norm not in expanded_exclusions and not any(exc in norm for exc in expanded_exclusions):
                active_norm_user_ing_map[norm] = raw

        norm_user_ings = list(active_norm_user_ing_map.keys())
        norm_user_ing_map = active_norm_user_ing_map

        if not norm_user_ings:
            return {"error": "All provided ingredients were excluded by constraints.", "results": [], "eligible_matches_found": 0}

        # Build query to fetch candidate recipes containing AT LEAST ONE of the user's ingredients
        fts_query = " OR ".join(norm_user_ings)

        with get_db() as conn:
            cur = conn.cursor()
            
            # 1. Fetch potential candidates using FTS index
            # Candidate must match at least one ingredient
            cur.execute("""
                SELECT r.id, r.title, r.ingredients_json, r.instructions,
                       r.ingredient_count, r.step_count, r.ingredients_clean
                FROM recipes r
                JOIN recipes_fts fts ON r.id = fts.id
                WHERE recipes_fts MATCH ?
                LIMIT 1500
            """, [fts_query])
            
            candidates = cur.fetchall()

        eligible_recipes = []
        violated_recipes = []

        for row in candidates:
            r_id = row["id"]
            title = row["title"]
            raw_ingredients = json.loads(row["ingredients_json"])
            instructions = row["instructions"]
            step_count = row["step_count"]
            ingredients_clean = row["ingredients_clean"].lower()

            # Check Hard Constraint 1: Exclusions (e.g. no peanuts)
            violated_exclusion = None
            for exc in expanded_exclusions:
                if exc in ingredients_clean:
                    violated_exclusion = exc
                    break

            # Check Hard Constraint 2: Max Steps
            violated_steps = False
            if max_steps is not None and step_count > max_steps:
                violated_steps = True

            # Match analysis
            matched = []
            recipe_items_matched_indices = set()

            for u_norm in norm_user_ings:
                # Check if u_norm appears in any raw ingredient
                found = False
                for idx, r_item in enumerate(raw_ingredients):
                    cleaned_item = clean_recipe_ingredient_item(r_item)
                    if u_norm in cleaned_item or u_norm in r_item.lower():
                        found = True
                        recipe_items_matched_indices.add(idx)
                if found:
                    matched.append(norm_user_ing_map[u_norm])

            # Additional ingredients needed by the recipe
            missing_ingredients = [
                raw_ingredients[idx] for idx in range(len(raw_ingredients))
                if idx not in recipe_items_matched_indices
            ]

            match_count = len(matched)
            missing_count = len(missing_ingredients)

            # Skip recipes that matched 0 of the user's ingredients
            if match_count == 0:
                continue

            # Calculate explainable score:
            # - Primary priority: Matched ingredients count (higher is better)
            # - Secondary priority: Fewer missing/additional ingredients
            # - Tertiary priority: Fewer instruction steps
            score = (match_count * 100) - (missing_count * 5)
            if prefer_fewer_steps:
                score -= (step_count * 2)

            recipe_record = {
                "id": r_id,
                "title": title,
                "score": score,
                "step_count": step_count,
                "matched_ingredients": matched,
                "matched_count": match_count,
                "missing_ingredients": missing_ingredients,
                "missing_count": missing_count,
                "total_recipe_ingredients": len(raw_ingredients),
                "instructions_preview": (instructions[:120] + "...") if len(instructions) > 120 else instructions
            }

            if violated_exclusion or violated_steps:
                reasons = []
                if violated_exclusion:
                    reasons.append(f"Contains excluded '{violated_exclusion}'")
                if violated_steps:
                    reasons.append(f"Exceeds max steps ({step_count} > {max_steps})")
                recipe_record["violation_reason"] = ", ".join(reasons)
                violated_recipes.append(recipe_record)
            else:
                eligible_recipes.append(recipe_record)

        # Sort eligible recipes by score descending, then step_count ascending
        eligible_recipes.sort(
            key=lambda x: (x["matched_count"], -x["missing_count"], -x["step_count"]),
            reverse=True
        )

        ranked_results = eligible_recipes[:limit]

        # Generate ranking explanations
        for rank, r in enumerate(ranked_results, 1):
            r["rank"] = rank
            r["explanation"] = (
                f"Rank #{rank}: Matches {r['matched_count']}/{len(norm_user_ings)} of your ingredients "
                f"({', '.join(r['matched_ingredients'])}), requires {r['missing_count']} additional ingredient(s), "
                f"and takes {r['step_count']} instruction steps."
            )

        quantity_notice = None
        if has_quantities:
            quantity_notice = (
                "Notice: Ingredient quantities were specified, but the dataset stores ingredient lines as "
                "unstructured text without standardized portion conversions. Matches are evaluated at the "
                "ingredient name level, and quantity sufficiency could not be strictly verified."
            )

        return {
            "user_ingredients": user_ingredients,
            "hard_exclusions": hard_exclusions,
            "max_steps": max_steps,
            "total_candidates_examined": len(candidates),
            "eligible_matches_found": len(eligible_recipes),
            "results": ranked_results,
            "closest_alternatives_violating_constraints": (
                sorted(violated_recipes, key=lambda x: x["matched_count"], reverse=True)[:3]
                if not ranked_results and violated_recipes else []
            ),
            "quantity_notice": quantity_notice
        }
