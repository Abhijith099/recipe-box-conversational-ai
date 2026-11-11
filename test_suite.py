"""
Automated verification test suite for Task 1 and Task 2 requirements.
Run with: python test_suite.py
"""

import unittest
from engine import RecipeEngine
from matcher import RecipeMatcher
from chat import ChatSession

class TestRecipeChatbot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = RecipeEngine()
        cls.matcher = RecipeMatcher()

    def setUp(self):
        self.session = ChatSession(self.engine, self.matcher)

    # ================= TASK 1 TESTS =================

    def test_total_dataset_size(self):
        """Verifies dataset size after filtering invalid records."""
        total = self.engine.get_total_recipe_count()
        self.assertEqual(total, 124595)

    def test_garlic_onion_cooccurrence(self):
        """Verifies exact count, percentage and denominator for garlic and onion."""
        res = self.engine.analyze_ingredient_cooccurrence(["garlic", "onion"])
        self.assertEqual(res["matching_count"], 20245)
        self.assertEqual(res["denominator"], 124595)
        self.assertAlmostEqual(res["percentage"], 16.25, places=2)

    def test_penne_pasta_search_and_dairy_refinement(self):
        """Tests conversational turn 1 (penne pasta) and turn 2 (dairy exclusion)."""
        turn1 = self.session.respond("Find a penne pasta recipe")
        self.assertIn("495", turn1)
        self.assertEqual(len(self.session.last_results), 5)

        turn2 = self.session.respond("I cannot have dairy")
        self.assertIn("dairy", self.session.active_exclusions)
        self.assertIn("101", turn2)

        # Verify no top result contains dairy keywords
        dairy_forbidden = ["butter", "milk", "cheese", "parmesan", "cream"]
        for r in self.session.last_results:
            ing_text = " ".join(r["ingredients"]).lower()
            for d in dairy_forbidden:
                self.assertNotIn(d, ing_text)

    def test_instruction_steps_ranking(self):
        """Tests ranking recipes containing tomato by fewest instruction steps."""
        res = self.engine.rank_by_instruction_steps("tomato", order="ASC", limit=5)
        self.assertEqual(len(res["recipes"]), 5)
        self.assertEqual(res["pool_size"], 19393)
        # Verify steps are non-decreasing
        steps = [r["step_count"] for r in res["recipes"]]
        self.assertEqual(steps, sorted(steps))

    def test_unavailable_attributes(self):
        """Verifies chatbot does not hallucinate unavailable nutritional or cooking time attributes."""
        res = self.session.respond("How many calories are in this recipe?")
        self.assertIn("Data Availability Notice", res)
        self.assertIn("does not record exact nutritional values", res)

    def test_show_recipe_details(self):
        """Verifies full instructions and ingredient list retrieval with stable ID."""
        self.session.respond("Find a penne pasta recipe")
        details = self.session.respond("Show recipe 1")
        self.assertIn("Stable Recipe ID", details)
        self.assertIn("Ingredients List:", details)
        self.assertIn("Instructions:", details)

    # ================= TASK 2 TESTS =================

    def test_ingredient_matching_exact_example(self):
        """
        Tests: User has eggs, onions, tomatoes, and rice.
        No peanuts, at most 6 instruction steps, prefer fewest additional ingredients.
        """
        res = self.matcher.match_recipes(
            user_ingredients=["eggs", "onions", "tomatoes", "rice"],
            hard_exclusions=["peanuts", "peanut"],
            max_steps=6,
            limit=5
        )
        self.assertTrue(res["eligible_matches_found"] > 0)
        self.assertEqual(len(res["results"]), 5)
        
        # Verify hard constraint: all results must have step_count <= 6
        for r in res["results"]:
            self.assertLessEqual(r["step_count"], 6)
            # Verify no peanuts
            for item in r["missing_ingredients"] + r["matched_ingredients"]:
                self.assertNotIn("peanut", item.lower())

        # Verify top result matches maximum ingredients
        top = res["results"][0]
        self.assertEqual(top["matched_count"], 4)
        self.assertIn("explanation", top)

    def test_matching_followup_exclusion(self):
        """Tests follow-up constraint: 'Exclude eggs too'."""
        self.session.respond("I have eggs, onions, tomatoes, and rice. Suggest five recipes with no peanuts and at most 6 instruction steps.")
        followup = self.session.respond("Exclude eggs too")
        
        self.assertIn("Exclude 'eggs'", followup)
        self.assertTrue(len(self.session.last_results) > 0)
        
        # Verify no recipe in results contains egg
        for r in self.session.last_results:
            self.assertNotIn("egg", r["matched_ingredients"])
            self.assertNotIn("eggs", r["matched_ingredients"])

    def test_hard_constraint_strictness_and_violations(self):
        """Tests that hard constraints are never relaxed silently."""
        # Query with an impossible constraint (e.g. max_steps = 0 with a complex ingredient)
        res = self.matcher.match_recipes(
            user_ingredients=["beef", "potatoes"],
            max_steps=0,
            limit=5
        )
        self.assertEqual(len(res["results"]), 0)
        self.assertEqual(res["eligible_matches_found"], 0)

    def test_task3_adaptation_banana_bread_no_eggs(self):
        """Tests Task 3: Banana bread recipe adaptation removing eggs with local dataset evidence."""
        res = self.session.respond("Take this banana bread recipe and remove eggs")
        self.assertIn("Task 3", res)
        self.assertIn("Applesauce", res)
        self.assertIn("Local Dataset Evidence", res)
        self.assertIn("Recipe ID:", res)
        self.assertIn("Revised Cooking Instructions", res)
        self.assertIn("Allergen Notice", res)

    def test_task3_adaptation_pasta_replace_cream_dairy_free(self):
        """Tests Task 3: Replace cream in pasta without dairy with local dataset evidence."""
        res = self.session.respond("Replace cream in this pasta recipe without dairy")
        self.assertIn("Task 3", res)
        self.assertIn("Coconut Milk", res)
        self.assertIn("Richness, fat content", res)
        self.assertIn("Recipe ID:", res)
        self.assertIn("Revised Cooking Instructions", res)

if __name__ == "__main__":
    unittest.main()
