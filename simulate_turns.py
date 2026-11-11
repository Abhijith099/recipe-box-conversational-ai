from chat import ChatSession

session = ChatSession()

test_conversation = [
    # Task 1: Search & Refinement
    "Find a penne pasta recipe",
    "I cannot have dairy",
    "Show recipe 1",
    
    # Task 2: Ingredient-Based Matching & Follow-up
    "I have eggs, onions, tomatoes, and rice. Suggest five recipes using as many of these as possible, with no peanuts and at most six instruction steps.",
    "Exclude eggs too",
    "Show recipe 1",
    
    # Task 1: Statistics & Attributes
    "How many recipes contain both garlic and onion? What percentage of the dataset is that?",
    "Among recipes containing tomato, which five have the fewest instruction steps?",
    "How many calories are in this recipe?"
]

for turn in test_conversation:
    print(f"\n========================================================")
    print(f"USER: {turn}")
    print(f"========================================================")
    reply = session.respond(turn)
    print(f"BOT:\n{reply}\n")
