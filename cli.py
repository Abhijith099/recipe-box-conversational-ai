"""
Interactive Command-Line Interface (CLI) for Recipe Box Chatbot.
Run with: python cli.py
"""

import sys
from chat import ChatSession

def print_banner():
    print("=" * 70)
    print("          RECIPE BOX CONVERSATIONAL CHATBOT          ")
    print("     Grounded Search, Analytics & Deterministic Q&A          ")
    print("=" * 70)
    print("Commands:")
    print("  - Type any question or search (e.g. 'Find a penne pasta recipe')")
    print("  - Ask follow-up restrictions (e.g. 'I cannot have dairy')")
    print("  - Ask statistics (e.g. 'How many recipes contain garlic and onion?')")
    print("  - Ask rankings (e.g. 'Among recipes with tomato, which have fewest steps?')")
    print("  - Type 'reset' to clear conversation context, or 'exit'/'quit' to leave.")
    print("=" * 70)
    print()

def main():
    print_banner()
    session = ChatSession()

    while True:
        try:
            user_input = input("\nYou > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye! Happy cooking!\n")
                break

            if user_input.lower() in ["reset", "clear"]:
                session.reset_state()
                print("\n[Conversation context and active filters cleared.]\n")
                continue

            response = session.respond(user_input)
            print(f"\nAssistant >\n{response}\n")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            sys.exit(0)

if __name__ == "__main__":
    main()

