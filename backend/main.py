#!/usr/bin/env python3
import os
import json
import argparse
import re
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
    
    def parse_conditions(self, conditions: str):
        """Parse conditions string and extract structured parameters"""
        if not conditions:
            return {
                'servings': 1,
                'cooking_time': None,
                'dietary_restrictions': [],
                'difficulty_level': 'medium',
                'flavor_profile': ''
            }
        
        conditions_lower = conditions.lower().strip()
        
        # Initialize defaults
        servings = 1
        cooking_time = None
        dietary_restrictions = []
        difficulty_level = 'medium'
        flavor_profile = ''
        
        # Parse servings - look for multiple patterns
        serving_patterns = [
            r'serves?\s+(\d+)',
            r'for\s+(\d+)\s+(?:people|persons?)',
            r'(\d+)\s+(?:servings?|people|persons?)',
            r'feeds?\s+(\d+)'
        ]
        
        for pattern in serving_patterns:
            match = re.search(pattern, conditions_lower)
            if match:
                servings = int(match.group(1))
                break
        
        # Parse cooking time - more precise matching
        time_patterns = [
            r'under\s+(\d+)\s*(?:mins?|minutes?)',
            r'less\s+than\s+(\d+)\s*(?:mins?|minutes?)',
            r'within\s+(\d+)\s*(?:mins?|minutes?)',
            r'in\s+(\d+)\s*(?:mins?|minutes?)',
            r'(\d+)\s*(?:mins?|minutes?)'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, conditions_lower)
            if match:
                minutes = int(match.group(1))
                if 'under' in pattern or 'less than' in pattern or 'within' in pattern:
                    cooking_time = f"under {minutes} minutes"
                else:
                    cooking_time = f"{minutes} minutes"
                break
        
        # Parse hours
        hour_patterns = [
            r'under\s+(\d+)\s*(?:hrs?|hours?)',
            r'(\d+)\s*(?:hrs?|hours?)'
        ]
        
        for pattern in hour_patterns:
            match = re.search(pattern, conditions_lower)
            if match:
                hours = int(match.group(1))
                if 'under' in pattern:
                    cooking_time = f"under {hours * 60} minutes"
                else:
                    cooking_time = f"{hours * 60} minutes"
                break
        
        # Parse dietary restrictions with better matching
        diet_mapping = {
            'vegetarian': ['veg', 'vegetarian'],
            'non-vegetarian': ['non-veg', 'non veg', 'nonveg', 'non vegetarian', 'nonvegetarian', 'meat'],
            'vegan': ['vegan'],
            'gluten-free': ['gluten free', 'gluten-free', 'glutenfree']
        }
        
        for diet_type, keywords in diet_mapping.items():
            if any(keyword in conditions_lower for keyword in keywords):
                dietary_restrictions.append(diet_type)
        
        # Parse difficulty level
        if any(word in conditions_lower for word in ['easy', 'simple', 'beginner']):
            difficulty_level = 'easy'
        elif any(word in conditions_lower for word in ['hard', 'difficult', 'complex', 'advanced']):
            difficulty_level = 'hard'
        elif any(word in conditions_lower for word in ['medium', 'moderate', 'intermediate']):
            difficulty_level = 'medium'
        
        # Parse flavor profiles
        flavor_keywords = {
            'spicy': ['spicy', 'hot', 'chili', 'chilli', 'pepper'],
            'sweet': ['sweet', 'sugary'],
            'sour': ['sour', 'tangy', 'acidic'],
            'mild': ['mild', 'gentle'],
            'savory': ['savory', 'savoury', 'umami'],
            'aromatic': ['aromatic', 'fragrant']
        }
        
        flavor_matches = []
        for flavor, keywords in flavor_keywords.items():
            if any(keyword in conditions_lower for keyword in keywords):
                flavor_matches.append(flavor)
        
        flavor_profile = ' '.join(flavor_matches) if flavor_matches else ''
        
        return {
            'servings': servings,
            'cooking_time': cooking_time,
            'dietary_restrictions': dietary_restrictions,
            'difficulty_level': difficulty_level,
            'flavor_profile': flavor_profile
        }
    
    def search_recipes(self, ingredients: List[str], conditions: str = None):
        """Search for recipes based on ingredients and conditions"""
        
        # Parse conditions into structured format
        parsed_conditions = self.parse_conditions(conditions)
        
        # Create query object
        query = RecipeQuery(
            ingredients=ingredients,
            dietary_restrictions=parsed_conditions['dietary_restrictions'] if parsed_conditions['dietary_restrictions'] else None,
            cooking_time=parsed_conditions['cooking_time'],
            difficulty_level=parsed_conditions['difficulty_level'],
            cuisine_type=None,  # Can be extended later
            servings=parsed_conditions['servings'],
            flavor_profile=parsed_conditions['flavor_profile'] if parsed_conditions['flavor_profile'] else None
        )
        
        # Process query
        result = self.rag_pipeline.process_query(query)
        
        # Display results
        self.display_recipe(result, parsed_conditions)
        
        return result
    
    def display_recipe(self, result, parsed_conditions):
        """Display the generated recipe in a formatted way"""
        recipe = result["recipe"]
        
        # Error handling for failed recipes
        if ("Unable to Create Recipe" in recipe.recipe_title or 
            "Invalid" in recipe.recipe_title or 
            "No Recipe Available" in recipe.recipe_title or
            "Error" in recipe.recipe_title):
            print(f"\n❌ {recipe.recipe_title}")
            print(f"📝 Issue: {recipe.instructions[0] if recipe.instructions else 'Unknown error'}")
            print(f"💡 Suggestion: {recipe.additional_notes}")
            return
        
        # Display successful recipe
        print("\n" + "="*60)
        print(f"🍳 {recipe.recipe_title}")
        print("="*60)
        
        # Show constraint compliance
        print(f"⏱️  Cooking Time: {recipe.cooking_time}")
        print(f"👨‍🍳 Difficulty: {recipe.difficulty.title()}")
        print(f"🍽️  Servings: {recipe.servings}")
        
        if parsed_conditions.get('dietary_restrictions'):
            diet_emojis = {
                'vegetarian': '🥬',
                'non-vegetarian': '🍖',
                'vegan': '🌱',
                'gluten-free': '🌾🚫'
            }
            diet_display = []
            for diet in parsed_conditions['dietary_restrictions']:
                emoji = diet_emojis.get(diet, '🍴')
                diet_display.append(f"{emoji} {diet.title()}")
            print(f"🥗 Diet: {', '.join(diet_display)}")
        
        if parsed_conditions.get('flavor_profile'):
            flavor_emojis = {
                'spicy': '🌶️',
                'sweet': '🍯',
                'sour': '🍋',
                'mild': '😌',
                'savory': '🧂',
                'aromatic': '🌿'
            }
            flavor_parts = parsed_conditions['flavor_profile'].split()
            flavor_display = []
            for flavor in flavor_parts:
                emoji = flavor_emojis.get(flavor, '👅')
                flavor_display.append(f"{emoji} {flavor.title()}")
            print(f"🌶️  Flavor: {', '.join(flavor_display)}")
        
        print(f"\n🥕 INGREDIENTS:")
        print("-" * 20)
        for i, ingredient in enumerate(recipe.ingredients, 1):
            # Add measurement indicators if missing
            if not any(measure in ingredient.lower() for measure in 
                      ['g', 'kg', 'ml', 'l', 'cup', 'tbsp', 'tsp', 'piece', 'clove', 'lb', 'oz']):
                if any(meat in ingredient.lower() for meat in ['chicken', 'beef', 'pork', 'fish', 'shrimp']):
                    ingredient = f"200-300g {ingredient}"
                elif 'rice' in ingredient.lower():
                    ingredient = f"1 cup {ingredient}"
                elif any(veg in ingredient.lower() for veg in ['onion', 'tomato', 'potato']):
                    ingredient = f"1-2 medium {ingredient}"
            print(f"{i:2d}. {ingredient}")
        
        print(f"\n📝 INSTRUCTIONS:")
        print("-" * 20)
        for i, instruction in enumerate(recipe.instructions, 1):
            # Wrap long instructions
            if len(instruction) > 80:
                words = instruction.split()
                lines = []
                current_line = []
                current_length = 0
                for word in words:
                    if current_length + len(word) + 1 <= 80:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_length = len(word)
                if current_line:
                    lines.append(" ".join(current_line))
                
                print(f"{i:2d}. {lines[0]}")
                for line in lines[1:]:
                    print(f"    {line}")
            else:
                print(f"{i:2d}. {instruction}")
        
        if recipe.additional_notes:
            print(f"\n💡 ADDITIONAL NOTES:")
            print("-" * 20)
            # Handle long notes
            notes = recipe.additional_notes
            if len(notes) > 80:
                words = notes.split()
                lines = []
                current_line = []
                current_length = 0
                for word in words:
                    if current_length + len(word) + 1 <= 80:
                        current_line.append(word)
                        current_length += len(word) + 1
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_length = len(word)
                if current_line:
                    lines.append(" ".join(current_line))
                for line in lines:
                    print(line)
            else:
                print(notes)
        
        # Show confidence and sources (optional - can be removed if not wanted)
        # confidence = result.get("confidence_score", 0)
        # print(f"\n📊 Recipe Confidence: {confidence:.1%}")
        # if result.get("chunks_retrieved", 0) > 0:
        #     print(f"📚 Knowledge Base Matches: {result['chunks_retrieved']}")
        # if result.get("web_recipes_found", 0) > 0:
        #     print(f"🌐 Web References: {result['web_recipes_found']}")
        
        print("\n" + "="*60)
    
    def interactive_mode(self):
        """Run in interactive mode with clean output"""
        print("\n🍳 Welcome to Recipe Generator!")
        print("Type 'exit' or 'quit' to leave")
        print("-" * 50)
        
        while True:
            try:
                print("\n📝 Enter your available ingredients (comma-separated):")
                ingredients_input = input("Ingredients: ").strip()
                
                if ingredients_input.lower() in ['exit', 'quit', 'q']:
                    break
                
                if not ingredients_input:
                    print("❌ Please enter at least one ingredient!")
                    continue
                
                # Clean and parse ingredients
                ingredients = [ing.strip() for ing in ingredients_input.split(',') if ing.strip()]
                if not ingredients:
                    print("❌ No valid ingredients found!")
                    continue
                
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
                
                # Search for recipes (no processing messages)
                result = self.search_recipes(ingredients, conditions)
                
                print("\n" + "-"*50)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye! Thanks for using Recipe Generator!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                continue

def main():
    parser = argparse.ArgumentParser(description="Advanced Recipe Generator using RAG")
    parser.add_argument("--ingest", type=str, help="Path to recipes JSON file for ingestion")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    parser.add_argument("--ingredients", type=str, help="Comma-separated ingredients")
    parser.add_argument("--conditions", type=str, help="Recipe conditions")
    
    args = parser.parse_args()
    
    # Initialize recipe generator
    try:
        generator = RecipeGenerator()
    except Exception as e:
        print(f"❌ Failed to initialize Recipe Generator: {e}")
        return
    
    try:
        # Handle data ingestion
        if args.ingest:
            print(f"📥 Starting ingestion from: {args.ingest}")
            success = generator.ingest_data(args.ingest)
            if not success:
                print("❌ Ingestion failed!")
                return
            print("✅ Ingestion completed!")
            
            # If only ingestion was requested, exit
            if not args.interactive and not args.ingredients:
                return
        
        # Handle direct recipe generation
        if args.ingredients:
            ingredients = [ing.strip() for ing in args.ingredients.split(',')]
            result = generator.search_recipes(ingredients, args.conditions)
            return
        
        # Handle interactive mode
        if args.interactive:
            generator.interactive_mode()
            return
        
        # Default behavior - show help
        if not any([args.ingest, args.interactive, args.ingredients]):
            print("🍳 Advanced Recipe Generator")
            print("=" * 50)
            print("\n🚀 USAGE OPTIONS:")
            print("\n1️⃣  Ingest recipe data:")
            print("   python backend/main.py --ingest data/recipes.json")
            
            print("\n2️⃣  Interactive mode:")
            print("   python backend/main.py --interactive")
            
            print("\n3️⃣  Direct generation:")
            print('   python backend/main.py --ingredients "chicken,rice,onion" --conditions "serves 4 veg under 30 mins"')
            
            print("\n🔧 FIRST-TIME SETUP:")
            print("1. Ingest data: python backend/main.py --ingest data/recipes.json")
            print("2. Use interactive: python backend/main.py --interactive")
            
            print("\n📋 CONDITION FORMAT:")
            print("• Servings: 'serves N', 'for N people', 'N servings'")
            print("• Time: 'under N mins', 'N minutes', 'less than N hours'")
            print("• Diet: 'vegetarian/veg', 'non-veg', 'vegan'")
            print("• Difficulty: 'easy', 'medium', 'hard'")
            print("• Flavor: 'spicy', 'sweet', 'mild', 'hot'")
            print("• Combine: 'serves 3 vegetarian under 25 mins medium spicy'")
    
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled. Goodbye!")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("🔧 Please check your setup and try again.")

if __name__ == "__main__":
    main()