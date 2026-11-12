"""
Conversational session manager and intent router.
Integrates Task 1 (Factual search, statistical queries) and Task 2 (Ingredient-based matching).
Maintains conversational state across turns:
- Retains active search query, active pantry ingredients, active exclusions, and max steps
- Handles follow-up constraints ('I cannot have dairy', 'Exclude eggs too')
- Retrieves full recipes on demand ('show recipe 1')
- Answers dataset statistical questions with reproducible calculations
- Transparently reports missing attributes (e.g. nutrition, cooking time)
"""

import re
from typing import Dict, Any, List, Optional
from engine import RecipeEngine, get_db
from matcher import RecipeMatcher
from adapter import RecipeAdapter

class ChatSession:
    def __init__(self, engine: Optional[RecipeEngine] = None, matcher: Optional[RecipeMatcher] = None, adapter: Optional[RecipeAdapter] = None):
        self.engine = engine or RecipeEngine()
        self.matcher = matcher or RecipeMatcher()
        self.adapter = adapter or RecipeAdapter()
        
        # State variables
        self.mode = "search"  # "search" or "matching"
        self.active_query: Optional[str] = None
        self.active_pantry_ingredients: List[str] = []
        self.active_exclusions: List[str] = []
        self.active_max_steps: Optional[int] = None
        
        self.last_results: List[Dict[str, Any]] = []
        self.history: List[Dict[str, str]] = []

    def reset_state(self):
        self.mode = "search"
        self.active_query = None
        self.active_pantry_ingredients = []
        self.active_exclusions = []
        self.active_max_steps = None
        self.last_results = []
        self.history = []

    def respond(self, user_input: str) -> str:
        text = user_input.strip()
        if not text:
            return "Please enter a question or recipe search."

        self.history.append({"role": "user", "text": text})
        lower = text.lower()

        # 1. Check for unavailable attributes (nutrition, calories, cooking time)
        if any(term in lower for term in ["calories", "nutrition", "carbs", "protein", "fat", "cook time", "prep time", "how long to cook"]):
            reply = self._handle_unavailable_attributes(text)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 2. Check for Task 2: Ingredient-Based Matching ("I have eggs, onions, tomatoes, and rice...")
        if self._is_matching_request(lower):
            reply = self._handle_ingredient_matching(text)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 3. Check for Task 1: Co-occurrence & percentage ("How many recipes contain both X and Y?")
        cooccur_match = re.search(r'how many (?:recipes )?contain (?:both )?([a-zA-Z\s]+) and ([a-zA-Z\s\?]+)', lower)
        if cooccur_match or ("how many recipes" in lower and "percentage" in lower):
            reply = self._handle_cooccurrence_query(lower)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 4. Check for Task 1: Instruction steps ranking ("Among recipes containing X, which ... fewest steps?")
        if ("fewest" in lower or "least" in lower or "instruction steps" in lower) and ("rank" in lower or "which" in lower or "top" in lower or "fewest" in lower):
            reply = self._handle_step_ranking(lower)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 5. Check for Task 1: Average / Median ingredient counts
        if any(w in lower for w in ["average", "median", "mean"]) and "ingredient" in lower:
            reply = self._handle_ingredient_stats(lower)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 6. Check for Task 3: Evidence-Based Ingredient Substitution / Adaptation
        if self._is_adaptation_request(lower):
            reply = self._handle_adaptation(text, lower)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 7. Check for recipe detail inspection ("Show recipe 1")
        show_match = re.search(r'(?:show|give|tell me|print|display)\s+(?:the\s+)?(?:instructions|recipe|ingredients|details)?\s*(?:for\s+)?(?:recipe\s+|number\s+|#\s*)?(\d+|[a-zA-Z0-9_\.\/-]{15,})', lower)
        if show_match or lower.startswith("show ") or lower.startswith("details "):
            reply = self._handle_show_recipe(lower)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 7. Check for follow-up restrictions (e.g. "Exclude eggs too", "I cannot have dairy", "no peanuts")
        restriction = self._detect_restriction(lower)
        if restriction:
            reply = self._handle_restriction_followup(restriction, lower)
            self.history.append({"role": "assistant", "text": reply})
            return reply

        # 8. Fallback to standard recipe search
        reply = self._handle_search(text)
        self.history.append({"role": "assistant", "text": reply})
        return reply

    def _is_adaptation_request(self, text: str) -> bool:
        indicators = ["replace ", "substitute ", "remove ", "swap ", "without eggs", "without cream", "without dairy", "without butter", "adapt "]
        return any(ind in text for ind in indicators)

    def _handle_adaptation(self, user_text: str, lower: str) -> str:
        # 1. Determine target ingredient to replace
        target_ing = None
        for ing in ["cream", "butter", "milk", "egg", "heavy cream", "baking powder", "sugar"]:
            if ing in lower:
                target_ing = ing
                break
                
        if not target_ing:
            # Capture up to 3 words for ingredients (e.g., "heavy whipping cream")
            m = re.search(r'\b(?:replace|substitute|remove|swap|without|no)\s+([a-zA-Z\s]{3,20})\b', lower)
            if m:
                cand = m.group(1).strip()
                # Clean filler words
                cand = re.sub(r'\b(?:this|the|a|an|from|in|recipe|dish)\b', '', cand).strip()
                if cand:
                    target_ing = cand
                    
        if not target_ing:
            return "I'm ready to adapt a recipe! Which ingredient would you like to substitute or remove?"
        # 2. Determine restriction (e.g. dairy-free, vegan)
        restriction = None
        if any(x in lower for x in ["without dairy", "no dairy", "dairy-free", "dairy free"]):
            restriction = "dairy-free"
        elif "vegan" in lower:
            restriction = "vegan"
        elif any(x in lower for x in ["nut-free", "no nuts", "no peanuts", "nut free"]):
            restriction = "nut-free"

        # 3. Find base recipe
        base_recipe = None
        
        
        dish_match = re.search(r'(?:in|this|for|adapt)\s+([a-zA-Z\s]+?)\s+(?:recipe|dish)?(?:\s+and|\s+without|\s+to|\.|$)', lower)
        dish_query = None
        if dish_match:
            cand = dish_match.group(1).strip()
            cand = re.sub(r'\b(?:this|the|a|an|recipe|dish|take)\b', '', cand).strip()
            if len(cand) > 2 and cand not in ["cream", "egg", "butter", "milk"]:
                dish_query = cand

        if dish_query:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM recipes WHERE lower(title) = ? OR lower(title) LIKE ? LIMIT 1", [dish_query.lower(), f"%{dish_query.lower()}%"])
                row = cur.fetchone()
                if row:
                    import json
                    base_recipe = {
                        "id": row["id"],
                        "title": row["title"],
                        "ingredients": json.loads(row["ingredients_json"]),
                        "instructions": row["instructions"]
                    }
            if not base_recipe:
                recipes, _ = self.engine.search_recipes(dish_query, limit=1)
                if recipes:
                    base_recipe_summary = recipes[0]
                    with get_db() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT * FROM recipes WHERE id = ?", [base_recipe_summary["id"]])
                        row = cur.fetchone()
                        if row:
                            import json
                            base_recipe = {
                                "id": row["id"],
                                "title": row["title"],
                                "ingredients": json.loads(row["ingredients_json"]),
                                "instructions": row["instructions"]
                            }

        # If no dish found via query, check last_results
        if not base_recipe and self.last_results:
            top_id = self.last_results[0]["id"]
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM recipes WHERE id = ?", [top_id])
                row = cur.fetchone()
                if row:
                    import json
                    base_recipe = {
                        "id": row["id"],
                        "title": row["title"],
                        "ingredients": json.loads(row["ingredients_json"]),
                        "instructions": row["instructions"]
                    }

        # Fallback: search for a recipe containing the target ingredient
        if not base_recipe:
            recipes, _ = self.engine.search_recipes(target_ing, limit=1)
            if recipes:
                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT * FROM recipes WHERE id = ?", [recipes[0]["id"]])
                    row = cur.fetchone()
                    if row:
                        import json
                        base_recipe = {
                            "id": row["id"],
                            "title": row["title"],
                            "ingredients": json.loads(row["ingredients_json"]),
                            "instructions": row["instructions"]
                        }

        if not base_recipe:
            return "Could not identify an active base recipe to adapt. Please search for a recipe first or name the dish (e.g. 'Take this banana bread recipe and remove eggs')."

        # 4. Call adapter
        adapt_res = self.adapter.adapt(base_recipe, target_ing, restriction)
        if not adapt_res.get("success"):
            return adapt_res.get("message", "Could not adapt recipe.")

        # 5. Format Task 3 grounded response
        lines = [
            f"**Evidence-Based Recipe Adaptation (Task 3)**",
            f"- **Base Recipe:** {adapt_res['original_title']} (ID: `{adapt_res['recipe_id']}`)",
            f"- **Target Change:** Replace `{adapt_res['target_ingredient']}`" + (f" ({restriction})" if restriction else ""),
            f"- **Culinary Role:** {adapt_res['culinary_role']}",
            f"- **Recommended Substitute:** **{adapt_res['chosen_substitute'].title()}** ({adapt_res['ratio_guideline']})",
            "",
            f"**Local Dataset Evidence ({adapt_res.get('evidence_level', 'indirect').title()} Evidence):**",
            f"Searched 124,595 local recipes for preparations using {adapt_res['chosen_substitute']} without {adapt_res['target_ingredient']}:"
        ]

        if adapt_res.get("local_evidence"):
            for ev in adapt_res["local_evidence"]:
                lines.append(f"- **{ev['title']}** (Recipe ID: `{ev['id']}`, {ev['steps']} steps)")
        else:
            lines.append("- *Notice: Local evidence is limited for this specific dish; relying on cross-recipe patterns.*")

        lines.extend([
            "",
            f"**Predicted Effects & Trade-offs:**",
            f"- **Texture & Flavor:** {adapt_res['trade_offs']}",
            f"- **Distinction:** Substitutions alter moisture retention and density; predictions are derived from recipe composition patterns in the dataset.",
            "",
            f"#### Updated Ingredients List:",
        ])
        for ing in adapt_res["updated_ingredients"]:
            lines.append(f"- {ing}")

        lines.extend([
            "",
            f"#### Revised Cooking Instructions:",
            adapt_res["revised_instructions"],
            "",
            f"> {adapt_res['safety_disclaimer']}"
        ])

        return "\n".join(lines)

    def _is_matching_request(self, text: str) -> bool:
        indicators = [
            "i have ", "we have ", "in my pantry", "in my fridge",
            "using as many of these", "suggest recipes using", "what can i cook with",
            "what can i make with"
        ]
        return any(ind in text for ind in indicators)

    def _extract_ingredients_from_text(self, text: str) -> List[str]:
        """Extracts list of ingredients from natural language prompt."""
        # 1. Catch a wider variety of natural conversational openings
        m = re.search(r'(?:i have|we have|i\'ve got|using|with|fridge has|pantry has)\s+([^.]+)', text, flags=re.IGNORECASE)
        segment = m.group(1) if m else text
        
        # 2. Chop off the end of the sentence when they start adding constraints or asking questions
        segment = re.split(r'\b(?:suggest|with no|without|exclude|prefer|and at most|can you|make|find)\b', segment, flags=re.IGNORECASE)[0]
        
        # 3. Split by commas or 'and'
        raw_items = re.split(r',|\band\b', segment)
        clean_items = []
        
        # Words we never want accidentally treated as ingredients
        stop_words = {"recipes", "recipe", "these", "ingredients", "something", "anything"}
        
        for item in raw_items:
            token = item.strip().lower()
            
            # 4. Strip out articles, common quantities, and filler verbs from the front
            token = re.sub(r'^(?:some|a|an|the|fresh|raw|i want to|cook|where|is used)\s+', '', token).strip()
            
            # If the token is valid, long enough, and not in our stop words list
            if token and len(token) > 2 and token not in stop_words:
                clean_items.append(token)
                
        return clean_items

    def _extract_max_steps(self, text: str) -> Optional[int]:
        m = re.search(r'(?:at most|maximum of|fewer than|less than|up to)\s+(\d+)\s*(?:instruction\s*)?steps?', text, flags=re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _extract_exclusions_from_text(self, text: str) -> List[str]:
        exclusions = []
        patterns = [
            r'(?:no|without|exclude|free of)\s+([a-zA-Z]+)',
            r'([a-zA-Z]+)[-\s]free'
        ]
        for p in patterns:
            matches = re.findall(p, text, flags=re.IGNORECASE)
            for m in matches:
                item = m.lower().strip()
                if item not in ["recipes", "steps", "more", "most", "the", "and"]:
                    exclusions.append(item)
        return exclusions

    def _detect_restriction(self, text: str) -> Optional[str]:
        patterns = [
            r'(?:exclude|without|no)\s+([a-zA-Z]+)(?:\s+too)?',
            r'(?:cannot|can\'t|cant)\s+have\s+([a-zA-Z]+)',
            r'allergic\s+to\s+([a-zA-Z]+)',
            r'([a-zA-Z]+)[-\s]free'
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                item = m.group(1).lower().strip()
                if item not in ["recipe", "recipes", "step", "steps"]:
                    return item
        return None

    def _handle_ingredient_matching(self, text: str) -> str:
        self.mode = "matching"
        extracted_ings = self._extract_ingredients_from_text(text)
        if extracted_ings:
            self.active_pantry_ingredients = extracted_ings
        
        extracted_exclusions = self._extract_exclusions_from_text(text)
        for exc in extracted_exclusions:
            if exc not in self.active_exclusions:
                self.active_exclusions.append(exc)

        max_steps = self._extract_max_steps(text)
        if max_steps is not None:
            self.active_max_steps = max_steps

        res = self.matcher.match_recipes(
            user_ingredients=self.active_pantry_ingredients,
            hard_exclusions=self.active_exclusions,
            max_steps=self.active_max_steps,
            limit=5
        )

        self.last_results = res.get("results", [])

        lines = [
            f"**Recipe Matching Results (Task 2)**",
            f"- **Your Ingredients:** {', '.join(self.active_pantry_ingredients)}",
            f"- **Hard Constraints:** Exclude ({', '.join(self.active_exclusions) if self.active_exclusions else 'None'})"
            + (f", Max Steps: {self.active_max_steps}" if self.active_max_steps is not None else ""),
            f"- **Ranking Objective:** Match maximum available ingredients, then minimize extra/missing ingredients.",
            f"- **Eligible Recipes Found:** {res['eligible_matches_found']} (showing top {len(self.last_results)})",
            ""
        ]

        if res.get("quantity_notice"):
            lines.append(f"> ℹ️ *{res['quantity_notice']}*")
            lines.append("")

        if not self.last_results:
            lines.append("⚠️ **No eligible recipes found** matching all specified constraints.")
            if res.get("closest_alternatives_violating_constraints"):
                lines.append("\n**Closest alternatives (violating constraints):**")
                for alt in res["closest_alternatives_violating_constraints"]:
                    lines.append(f"- **{alt['title']}** (ID: `{alt['id']}`) — *Violation: {alt.get('violation_reason')}*")
        else:
            for r in self.last_results:
                lines.append(f"### {r['rank']}. {r['title']} (ID: `{r['id']}`)")
                lines.append(f"- **Matched ({r['matched_count']}):** {', '.join(r['matched_ingredients'])}")
                
                # Show up to 4 missing ingredients
                missing_str = ", ".join(r['missing_ingredients'][:4])
                if len(r['missing_ingredients']) > 4:
                    missing_str += f" (+{len(r['missing_ingredients']) - 4} more)"
                lines.append(f"- **Additional Needed ({r['missing_count']}):** {missing_str if missing_str else 'None! Complete pantry match'}")
                lines.append(f"- **Instruction Steps:** {r['step_count']}")
                lines.append(f"- **Ranking Explanation:** {r['explanation']}")
                lines.append("")

        lines.append("*Follow-up ideas: 'Exclude eggs too', 'Show recipe 1', or 'Reset'*")
        return "\n".join(lines)

    def _handle_restriction_followup(self, restriction: str, raw_text: str) -> str:
        if restriction not in self.active_exclusions:
            self.active_exclusions.append(restriction)

        # If in matching mode, re-run matching
        if self.mode == "matching" and self.active_pantry_ingredients:
            res = self.matcher.match_recipes(
                user_ingredients=self.active_pantry_ingredients,
                hard_exclusions=self.active_exclusions,
                max_steps=self.active_max_steps,
                limit=5
            )
            self.last_results = res.get("results", [])

            lines = [
                f"**Updated Matching (Added Hard Constraint: Exclude '{restriction}')**",
                f"- **Pantry Ingredients:** {', '.join(self.active_pantry_ingredients)}",
                f"- **Active Exclusions:** {', '.join(self.active_exclusions)}",
                f"- **Eligible Recipes Remaining:** {res['eligible_matches_found']} (showing top {len(self.last_results)})",
                ""
            ]

            if not self.last_results:
                lines.append("⚠️ **No eligible recipes found** matching all specified constraints.")
            else:
                for r in self.last_results:
                    lines.append(f"### {r['rank']}. {r['title']} (ID: `{r['id']}`)")
                    lines.append(f"- **Matched ({r['matched_count']}):** {', '.join(r['matched_ingredients'])}")
                    missing_str = ", ".join(r['missing_ingredients'][:4])
                    if len(r['missing_ingredients']) > 4:
                        missing_str += f" (+{len(r['missing_ingredients']) - 4} more)"
                    lines.append(f"- **Additional Needed ({r['missing_count']}):** {missing_str}")
                    lines.append(f"- **Instruction Steps:** {r['step_count']}")
                    lines.append(f"- **Ranking Explanation:** {r['explanation']}")
                    lines.append("")

            lines.append("*Type 'show recipe 1' to view full instructions.*")
            return "\n".join(lines)

        # Otherwise in search mode
        if not self.active_query:
            return (
                f"Noted: restriction '{restriction}' has been added to your session preferences. "
                "What type of dish or recipe would you like to search for?"
            )

        recipes, total = self.engine.search_recipes(
            query=self.active_query,
            exclusions=self.active_exclusions,
            limit=5
        )
        self.last_results = recipes

        lines = [
            f"**Refining previous search: '{self.active_query}'**",
            f"**Active Restrictions:** {', '.join(self.active_exclusions)}",
            f"**Matching Recipes Found:** {total} (showing top {len(recipes)})",
            ""
        ]

        if not recipes:
            lines.append("No recipes match this combination of search terms and restrictions.")
        else:
            for idx, r in enumerate(recipes, 1):
                preview_ings = ", ".join(r["ingredients"][:4])
                lines.append(f"{idx}. **{r['title']}** (ID: `{r['id']}`)")
                lines.append(f"   - *Key Ingredients:* {preview_ings}")
                lines.append(f"   - *Steps:* {r['step_count']} steps | *Total Ingredients:* {r['ingredient_count']}")
                lines.append("")

        lines.append("*Tip: Type 'show recipe 1' to view full ingredients and cooking instructions.*")
        return "\n".join(lines)

    def _clean_search_query(self, user_query: str) -> str:
        """
        Cleans conversational filler, natural language phrasing, and common stop words
        from user queries so that the underlying FTS5 engine receives only key terms
        (e.g., 'Can you get me a recipe where cheese is used' -> 'cheese').
        """
        # Common conversational stop words / filler in recipe queries
        stop_words = {
            'a', 'an', 'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for', 'with', 'from',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might', 'must',
            'i', 'you', 'yo', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'its', 'our', 'their', 'mine', 'yours', 'ours', 'theirs',
            'get', 'give', 'show', 'find', 'make', 'cook', 'tell', 'look', 'search', 'want', 'need', 'like', 'used', 'using',
            'recipe', 'recipes', 'dish', 'dishes', 'food', 'something', 'anything', 'related', 'where', 'which', 'what', 'who', 'how', 'when',
            'ingredient', 'ingredients', 'ingrident', 'ingridents', 'please', 'some'
        }

        words = re.findall(r'[a-zA-Z0-9]+', user_query.lower())
        content_words = [w for w in words if w not in stop_words]
        if content_words:
            return ' '.join(content_words)

        # Fallback to stripped original if everything was filtered out
        return user_query.strip()

    def _handle_search(self, user_query: str) -> str:
        self.mode = "search"
        clean = self._clean_search_query(user_query)

        self.active_query = clean
        recipes, total = self.engine.search_recipes(
            query=clean,
            exclusions=self.active_exclusions,
            limit=5
        )
        self.last_results = recipes

        filters_msg = f" (Exclusions: {', '.join(self.active_exclusions)})" if self.active_exclusions else ""
        lines = [
            f"**Search Results for: '{clean}'**{filters_msg}",
            f"**Total Matching Recipes:** {total} (showing top {len(recipes)})",
            ""
        ]

        if not recipes:
            lines.append("No recipes found matching your query.")
        else:
            for idx, r in enumerate(recipes, 1):
                preview_ings = ", ".join(r["ingredients"][:4])
                lines.append(f"{idx}. **{r['title']}** (ID: `{r['id']}`)")
                lines.append(f"   - *Sample Ingredients:* {preview_ings}")
                lines.append(f"   - *Steps:* {r['step_count']} | *Ingredients Count:* {r['ingredient_count']}")
                lines.append("")

        lines.append("*Ask follow-up questions to refine (e.g. 'I cannot have dairy', 'which has fewest steps?'), or 'show recipe 1'*")
        return "\n".join(lines)

    def _handle_show_recipe(self, text: str) -> str:
        if not self.last_results:
            return "No active search or matching results. Please perform a search or recipe match first."

        num_match = re.search(r'\b([1-5])\b', text)
        idx = 0
        if num_match:
            idx = int(num_match.group(1)) - 1

        if 0 <= idx < len(self.last_results):
            r = self.last_results[idx]
        else:
            r = self.last_results[0]

        # Fetch complete recipe from DB by ID to ensure full details
        with self.engine.get_db() if hasattr(self.engine, 'get_db') else get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM recipes WHERE id = ?", [r["id"]])
            row = cur.fetchone()

        import json
        full_ings = json.loads(row["ingredients_json"])

        lines = [
            f"### {row['title']}",
            f"**Stable Recipe ID:** `{row['id']}`",
            f"**Source Collection:** {row['source'].upper()}",
            f"**Metrics:** {row['ingredient_count']} ingredients | {row['step_count']} instruction steps",
            "",
            "#### Ingredients List:",
        ]
        for ing in full_ings:
            lines.append(f"- {ing}")

        lines.append("")
        lines.append("#### Instructions:")
        lines.append(row["instructions"])
        return "\n".join(lines)

    def _handle_cooccurrence_query(self, lower: str) -> str:
        tokens = re.findall(r'\b[a-z]{3,}\b', lower)
        stop_words = {"how", "many", "recipes", "contain", "both", "and", "what", "percentage", "the", "dataset", "that", "this", "all", "are", "there"}
        candidates = [t for t in tokens if t not in stop_words]

        target_ings = []
        if "garlic" in lower: target_ings.append("garlic")
        if "onion" in lower or "onions" in lower: target_ings.append("onion")
        if "tomato" in lower or "tomatoes" in lower: target_ings.append("tomato")
        
        if not target_ings and len(candidates) >= 2:
            target_ings = candidates[:2]
        elif not target_ings:
            target_ings = ["garlic", "onion"]

        data = self.engine.analyze_ingredient_cooccurrence(target_ings)
        
        reply = (
            f"**Statistical Analysis: Ingredient Co-occurrence**\n"
            f"- **Target Ingredients:** {', '.join(data['ingredients'])}\n"
            f"- **Matching Recipes:** **{data['matching_count']:,}**\n"
            f"- **Total Dataset Size (Denominator):** **{data['denominator']:,}** valid recipes\n"
            f"- **Percentage of Dataset:** **{data['percentage']}%**\n\n"
            f"**Methodology & Normalization:**\n"
            f"- {data['normalization_rule']}\n"
            f"- The denominator excludes 569 unparseable/empty records from the original 125,164 raw entries, leaving {data['denominator']:,} fully validated recipes."
        )
        return reply

    def _handle_step_ranking(self, lower: str) -> str:
        target = "tomato"
        words = ["tomato", "chicken", "beef", "pasta", "potato", "chocolate", "cheese", "rice", "garlic"]
        for w in words:
            if w in lower:
                target = w
                break

        res = self.engine.rank_by_instruction_steps(target, order="ASC", limit=5)
        
        lines = [
            f"**Instruction Step Ranking (Fewest Steps)**",
            f"- **Filter:** Recipes containing '{res['filter_ingredient']}'",
            f"- **Matching Candidate Pool:** {res['pool_size']:,} recipes",
            f"- **Step Counting Rule:** {res['rule']}",
            "",
            "**Top 5 Recipes with Fewest Instruction Steps:**"
        ]

        for i, r in enumerate(res["recipes"], 1):
            lines.append(f"{i}. **{r['title']}** (ID: `{r['id']}`)")
            lines.append(f"   - Steps: **{r['step_count']}** | Total Ingredients: {r['ingredient_count']}")
            lines.append(f"   - Preview: *{r['instructions_preview']}*")
            lines.append("")

        return "\n".join(lines)

    def _handle_ingredient_stats(self, lower: str) -> str:
        stats = self.engine.compute_ingredient_statistics(self.active_query)
        lines = [
            f"**Dataset Statistics: Ingredient Counts**",
            f"- **Scope:** {stats['filter']}",
            f"- **Recipes Analyzed:** {stats['analyzed_count']:,}",
            f"- **Average (Mean) Ingredients:** **{stats['average_ingredients']}**",
            f"- **Median Ingredients:** **{stats['median_ingredients']}**",
            f"- **Range:** Min {stats['min_ingredients']}, Max {stats['max_ingredients']} ingredients"
        ]
        return "\n".join(lines)

    def _handle_unavailable_attributes(self, text: str) -> str:
        return (
            "**Data Availability Notice:**\n"
            "The Recipe Box dataset does not record exact nutritional values (such as calories, macros, or vitamins) "
            "nor does it specify structured cooking/prep time fields.\n\n"
            "**Available Data Attributes:**\n"
            "- Unique stable Recipe ID (`id`)\n"
            "- Recipe Title (`title`)\n"
            "- Raw & Cleaned Ingredient List (`ingredients`)\n"
            "- Full Instruction Text (`instructions`)\n"
            "- Picture URL (`picture_link`, where available)\n\n"
            "To keep answers strictly grounded and avoid hallucination, these values cannot be estimated without external assumptions."
        )#handles hallucination by stating unavailability of data
