"""Quick test of Tier 5 Gemini integration."""
from dotenv import load_dotenv
load_dotenv()

from pipeline.categorization.tier5_llm import classify, GEMINI_MODEL, ENABLED, GEMINI_API_KEY

print(f"ENABLED: {ENABLED}")
print(f"MODEL: {GEMINI_MODEL}")
print(f"KEY set: {bool(GEMINI_API_KEY)}")
print()

tests = [
    "BESCOM electricity bill",
    "HP Gas LPG refill",
    "BigBasket grocery order",
    "Zomato food delivery",
    "random unknown xyz abc",
]

for merchant in tests:
    result = classify(merchant)
    if result:
        print(f"OK  [{merchant}] -> {result.category} (conf={result.confidence:.2f}, tier={result.tier})")
    else:
        print(f"--- [{merchant}] -> None (no result / disabled)")
