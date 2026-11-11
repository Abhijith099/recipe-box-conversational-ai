"""
Core grounded search and analytics engine for the Recipe Box dataset.
Provides deterministic data operations:
- Full-text search with title and ingredient matching
- Negative restrictions (dietary filters like dairy, gluten, nuts)
- Analytical calculations (counts, percentages, median, mean)
- Instruction step ranking and step-counting explanations
"""

import json
import re
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

DB_PATH = "recipes.db"

# Common dietary restriction ingredient keywords
RESTRICTION_KEYWORDS = {
    "dairy": [
        "milk", "butter", "cheese", "cream", "yogurt", "sour cream",
        "parmesan", "cheddar", "mozzarella", "ricotta", "ghee", "half-and-half",
        "whey", "buttermilk", "cream cheese", "heavy cream"
    ],
    "gluten": [
        "flour", "wheat", "bread", "pasta", "soy sauce", "barley", "rye"
    ],
    "nuts": [
        "peanut", "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut"
    ],
    "meat": [
        "chicken", "pork", "bacon", "turkey", "lamb", "sausage", "ham", "veal"
    ]
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class RecipeEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_total_recipe_count(self) -> int:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM recipes")
            return cur.fetchone()[0]

    def search_recipes(
        self,
        query: str,
        exclusions: Optional[List[str]] = None,
        limit: int = 5
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Searches recipes by keywords in title and ingredients, applying exclusions.
        Returns (list_of_recipes, total_matching_count).
        """
        exclusions = exclusions or []
        tokens = [t.strip().replace("'", "''") for t in re.findall(r'\w+', query) if len(t.strip()) > 1]
        if not tokens:
            return [], 0

        fts_query = " AND ".join(tokens)

        with get_db() as conn:
            cur = conn.cursor()
            
            # Base query fetching candidate IDs
            sql = """
                SELECT r.id, r.source, r.raw_id, r.title, r.ingredients_json,
                       r.instructions, r.ingredient_count, r.step_count, r.ingredients_clean
                FROM recipes r
                JOIN recipes_fts fts ON r.id = fts.id
                WHERE recipes_fts MATCH ?
            """
            params = [fts_query]

            # If exclusions exist, expand them to sub-keywords
            exclusion_words = []
            for exc in exclusions:
                exc_lower = exc.lower().strip()
                if exc_lower in RESTRICTION_KEYWORDS:
                    exclusion_words.extend(RESTRICTION_KEYWORDS[exc_lower])
                else:
                    exclusion_words.append(exc_lower)

            # Filter out excluded words
            for exc_word in exclusion_words:
                sql += " AND lower(r.ingredients_clean) NOT LIKE ?"
                params.append(f"%{exc_word}%")

            # Count total matching records before limit
            count_sql = f"SELECT COUNT(*) FROM ({sql})"
            cur.execute(count_sql, params)
            total_matches = cur.fetchone()[0]

            # Fetch top results
            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)
            
            cur.execute(sql, params)
            rows = cur.fetchall()

            results = []
            for r in rows:
                results.append({
                    "id": r["id"],
                    "source": r["source"],
                    "raw_id": r["raw_id"],
                    "title": r["title"],
                    "ingredients": json.loads(r["ingredients_json"]),
                    "instructions": r["instructions"],
                    "ingredient_count": r["ingredient_count"],
                    "step_count": r["step_count"]
                })

            return results, total_matches

    def analyze_ingredient_cooccurrence(self, ingredients: List[str]) -> Dict[str, Any]:
        """
        Calculates exact count and percentage of recipes containing all given ingredients.
        Provides denominator and normalization explanation.
        """
        total_recipes = self.get_total_recipe_count()
        clean_ingredients = [ing.strip().lower() for ing in ingredients if ing.strip()]
        
        if not clean_ingredients:
            return {"error": "No ingredients specified"}

        fts_query = " AND ".join(clean_ingredients)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT count(*) 
                FROM recipes_fts 
                WHERE ingredients MATCH ?
            """, [fts_query])
            count = cur.fetchone()[0]

        pct = (count / total_recipes) * 100 if total_recipes > 0 else 0.0

        return {
            "ingredients": clean_ingredients,
            "matching_count": count,
            "denominator": total_recipes,
            "percentage": round(pct, 2),
            "normalization_rule": (
                "Ingredients are normalized using full-text Porter stemming and case-insensitive matching. "
                "Matches include variations like singular/plural (e.g. 'onion' matches 'onions', 'garlic' matches 'garlic cloves')."
            )
        }

    def rank_by_instruction_steps(
        self,
        filter_ingredient: str,
        order: str = "ASC",
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Ranks recipes matching a filter by instruction step count.
        """
        order_direction = "ASC" if order.upper() == "ASC" else "DESC"
        with get_db() as conn:
            cur = conn.cursor()
            
            # Count total pool of matching recipes
            cur.execute("""
                SELECT count(*) FROM recipes_fts WHERE ingredients MATCH ?
            """, [filter_ingredient])
            pool_size = cur.fetchone()[0]

            # Fetch ranked items
            cur.execute(f"""
                SELECT r.id, r.title, r.step_count, r.ingredient_count, r.instructions
                FROM recipes r
                JOIN recipes_fts fts ON r.id = fts.id
                WHERE fts.ingredients MATCH ?
                ORDER BY r.step_count {order_direction}, length(r.instructions) ASC
                LIMIT ?
            """, [filter_ingredient, limit])
            
            rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "title": r["title"],
                "step_count": r["step_count"],
                "ingredient_count": r["ingredient_count"],
                "instructions_preview": (r["instructions"][:150] + "...") if len(r["instructions"]) > 150 else r["instructions"]
            })

        return {
            "filter_ingredient": filter_ingredient,
            "pool_size": pool_size,
            "order": order_direction,
            "rule": "Instruction steps are calculated by splitting on paragraph breaks and sentence boundary markers (period/exclamation followed by whitespace and capital letter/number).",
            "recipes": results
        }

    def compute_ingredient_statistics(self, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculates average, median, min, max ingredient counts over all recipes or a subset.
        """
        total_denom = self.get_total_recipe_count()
        with get_db() as conn:
            cur = conn.cursor()
            if query:
                cur.execute("""
                    SELECT r.ingredient_count
                    FROM recipes r
                    JOIN recipes_fts fts ON r.id = fts.id
                    WHERE recipes_fts MATCH ?
                    ORDER BY r.ingredient_count ASC
                """, [query])
            else:
                cur.execute("SELECT ingredient_count FROM recipes ORDER BY ingredient_count ASC")

            counts = [row[0] for row in cur.fetchall()]

        if not counts:
            return {"error": "No recipes found for the given criteria."}

        n = len(counts)
        avg_count = sum(counts) / n
        if n % 2 == 1:
            median_count = counts[n // 2]
        else:
            median_count = (counts[(n // 2) - 1] + counts[n // 2]) / 2.0

        return {
            "filter": query if query else "Entire dataset",
            "analyzed_count": n,
            "total_dataset_size": total_denom,
            "average_ingredients": round(avg_count, 2),
            "median_ingredients": median_count,
            "min_ingredients": counts[0],
            "max_ingredients": counts[-1]
        }
