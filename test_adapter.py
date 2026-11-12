import json
from pathlib import Path

# Load test recipes from the external JSON file
data_path = Path(__file__).parent / "test_recipes.json"
with open(data_path, "r", encoding="utf-8") as f:
    RAW_TEST_RECIPES = json.load(f)

# Then unpack and insert them into your in-memory SQLite fixture:
recipes_tuples = [
    (
        r["id"], r["source"], r["raw_id"], r["title"],
        json.dumps(r["ingredients_json"], ensure_ascii=False),
        r["instructions"], r["picture_link"], r["ingredient_count"],
        r["step_count"], r["ingredients_clean"]
    )
    for r in RAW_TEST_RECIPES
]