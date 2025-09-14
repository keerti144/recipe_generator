#!/usr/bin/env python3
import os
import json
import argparse
from typing import List
from dotenv import load_dotenv
from models import RecipeQuery
from rag_pipeline import RAGPipeline

load_dotenv()

class RecipeGenerator:
    def __init__(self):
        print("Initializing Recipe Generator...")
        self.rag_pipeline = RAGPipeline()
        print("Recipe Generator initialized successfully!")
    
    def ingest_data(self, recipes_file: str):
        """Ingest recipe data from JSON file"""
        if not os.path.exists(recipes_file):
            print(f"Error: Recipe file {recipes_file} not found!")
            return False
        
        print(f"Starting data ingestion from {recipes_file}...")
        success = self.rag_pipeline.ingest_recipes(recipes_file)
        
        if success:
            print("Data ingestion completed successfully!")
        else:
            print("Data ingestion failed!")
        
        return success
    
    def search_recipes(self, ingredients: List[str], conditions: str = None):
        """Search for recipes based on ingredients and conditions"""
        # Parse conditions
        cooking_time = None
        difficulty_level = None
        dietary_restrictions = []
        cuisine_type = None
        servings = 1  # Default to 1 serving if not specified
        
        if conditions:
            conditions_lower = conditions.lower()
            
            # Parse cooking time
            if "under" in conditions_lower or "less than" in conditions_lower:
                if "min" in conditions_lower:
                    for word in conditions_lower.split():
                        if word.replace("mins", "").replace("min", "").isdigit():
                            cooking_time = f"under {word.replace('mins', '').replace('min', '')} minutes"
                            break
            
            # Parse difficulty
            if "easy" in conditions_lower:
                difficulty_level = "easy"
            elif "medium" in conditions_lower:
                difficulty_level = "medium"
            elif "hard" in conditions_lower or "difficult" in conditions_lower:
                difficulty_level = "hard"
            
            # Parse dietary restrictions
            if "vegetarian" in conditions_lower:
                dietary_restrictions.append("vegetarian")
            if "vegan" in conditions_lower:
                dietary_restrictions.append("vegan")
            if "gluten-free" in conditions_lower:
                dietary_restrictions.append("gluten-free")
            
            # Parse servings with better logic
            servings_found = False
            for word in conditions_lower.replace(",", " ").split():
                # Clean the word and check if it's a number
                clean_word = word.replace("people", "").replace("person", "").replace("servings", "").replace("serves", "").replace("serving", "")
                if clean_word.isdigit():
                    servings = int(clean_word)
                    servings_found = True
                    break
            
            # Look for specific serving patterns
            if not servings_found:
                import re
                # Match patterns like "serves 4", "for 6 people", "4 servings"
                serving_patterns = [
                    r'serves?\s+(\d+)',
                    r'for\s+(\d+)\s+(?:people|person)',
                    r'(\d+)\s+(?:servings?|people|persons?)',
                    r'feeds?\s+(\d+)'
                ]
                
                for pattern in serving_patterns:
                    match = re.search(pattern, conditions_lower)
                    if match:
                        servings = int(match.group(1))
                        break
        
        # Ensure servings is always at least 1
        if servings is None or servings < 1:
            servings = 1
        
        # Create query
        query = RecipeQuery(
            ingredients=ingredients,
            dietary_restrictions=dietary_restrictions if dietary_restrictions else None,
            cooking_time=cooking_time,
            difficulty_level=difficulty_level,
            cuisine_type=cuisine_type,
            servings=servings
        )
        
        # Process query
        result = self.rag_pipeline.process_query(query)
        
        # Display recipe results
        self.display_recipe(result)
        
        return result
    
    def display_recipe(self, result):
        """Display the generated recipe in a formatted way"""
        recipe = result["recipe"]
        
        # Simple error display for invalid ingredients
        if "Unable to Create Recipe" in recipe.recipe_title or "Invalid" in recipe.recipe_title:
            print(f"\n❌ {recipe.recipe_title}")
            print(f"💡 {recipe.additional_notes}")
            return
        
        print("\n" + "="*60)
        print(f"🍳 {recipe.recipe_title}")
        print("="*60)
        
        print(f"⏱️  Cooking Time: {recipe.cooking_time}")
        print(f"👨‍🍳 Difficulty: {recipe.difficulty.capitalize()}")
        print(f"🍽️  Servings: {recipe.servings}")
        
        print(f"\n🥕 INGREDIENTS:")
        print("-" * 20)
        for i, ingredient in enumerate(recipe.ingredients, 1):
            print(f"{i:2d}. {ingredient}")
        
        print(f"\n📝 INSTRUCTIONS:")
        print("-" * 20)
        for i, instruction in enumerate(recipe.instructions, 1):
            print(f"{i:2d}. {instruction}")
        
        if recipe.additional_notes:
            print(f"\n💡 ADDITIONAL NOTES:")
            print("-" * 20)
            print(recipe.additional_notes)
        
        print("\n" + "="*60)
    
    def interactive_mode(self):
        """Run in interactive mode"""
        print("\n🍳 Welcome to Recipe Generator!")
        print("Type 'exit' or 'quit' to leave")
        print("-" * 50)
        
        while True:
            try:
                print("\n📝 Enter your available ingredients (comma-separated):")
                ingredients_input = input("Ingredients: ").strip()
                
                if ingredients_input.lower() in ['exit', 'quit']:
                    break
                
                if not ingredients_input:
                    print("Please enter at least one ingredient!")
                    continue
                
                ingredients = [ing.strip() for ing in ingredients_input.split(',')]
                
                print("\n⚙️  Enter any conditions (optional):")
                print("Examples:")
                print("  • 'under 15 mins' - for time constraints")
                print("  • 'vegetarian easy' - for dietary and difficulty")
                print("  • 'serves 4 people' or 'for 6 people' - for serving size")
                print("  • 'serves 2 vegetarian under 20 mins' - combined conditions")
                print("  • Leave empty for 1 serving, medium difficulty")
                conditions = input("Conditions: ").strip()
                
                if not conditions:
                    conditions = None
                
                # Search for recipes
                self.search_recipes(ingredients, conditions)
                
                print("\n" + "-"*50)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            except Exception as e:
                print(f"Error: {e}")
                continue

def main():
    parser = argparse.ArgumentParser(description="Recipe Generator using RAG")
    parser.add_argument("--ingest", type=str, help="Path to recipes JSON file for ingestion")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    # Initialize recipe generator
    generator = RecipeGenerator()
    
    try:
        # Handle data ingestion
        if args.ingest:
            success = generator.ingest_data(args.ingest)
            if not success:
                return
        
        # Handle interactive mode
        if args.interactive:
            generator.interactive_mode()
            return
        
        # Default behavior - show help
        if not any([args.ingest, args.interactive]):
            print("🍳 Recipe Generator")
            print("=" * 40)
            print("\nUsage:")
            print("1. Ingest recipe data:")
            print("   python backend/main.py --ingest data/recipes.json")
            print("\n2. Interactive mode:")
            print("   python backend/main.py --interactive")
            print("\nFor first-time setup:")
            print("1. Run ingestion: python backend/main.py --ingest data/recipes.json")
            print("2. Use interactive mode: python backend/main.py --interactive")
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user. Goodbye! 👋")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()