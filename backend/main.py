#!/usr/bin/env python3
import os
import re
from typing import List
from dotenv import load_dotenv
import streamlit as st

from models import RecipeQuery
from rag_pipeline import RAGPipeline

load_dotenv()

class RecipeGenerator:
    def __init__(self):
        self.rag_pipeline = RAGPipeline()

        # Ensure ingestion happens only once
        if "recipes_ingested" not in st.session_state:
            st.session_state["recipes_ingested"] = True
            recipes_file = os.path.join(os.path.dirname(__file__), "..", "data", "recipes.json")
            recipes_file = os.path.abspath(recipes_file)

            if os.path.exists(recipes_file):
                success = self.rag_pipeline.ingest_recipes(recipes_file)
                if success:
                    st.sidebar.success(f"✅ Recipes ingested from {recipes_file}")
                    st.session_state["recipes_ingested"] = True
                else:
                    st.sidebar.warning("⚠️ Recipe ingestion failed.")
            else:
                st.sidebar.warning(f"⚠️ Recipes file not found at {recipes_file}")

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

        # Defaults
        servings = 1
        cooking_time = None
        dietary_restrictions = []
        difficulty_level = 'medium'
        flavor_profile = ''

        # Servings
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

        # Cooking time
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

        # Hours
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

        # Diet
        diet_mapping = {
            'vegetarian': ['veg', 'vegetarian'],
            'non-vegetarian': ['non-veg', 'non veg', 'nonveg', 'non vegetarian', 'nonvegetarian', 'meat'],
            'vegan': ['vegan'],
            'gluten-free': ['gluten free', 'gluten-free', 'glutenfree']
        }
        for diet_type, keywords in diet_mapping.items():
            if any(keyword in conditions_lower for keyword in keywords):
                dietary_restrictions.append(diet_type)

        # Difficulty
        if any(word in conditions_lower for word in ['easy', 'simple', 'beginner']):
            difficulty_level = 'easy'
        elif any(word in conditions_lower for word in ['hard', 'difficult', 'complex', 'advanced']):
            difficulty_level = 'hard'
        elif any(word in conditions_lower for word in ['medium', 'moderate', 'intermediate']):
            difficulty_level = 'medium'

        # Flavor
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
        """Search for recipes and display in Streamlit"""
        parsed_conditions = self.parse_conditions(conditions)

        query = RecipeQuery(
            ingredients=ingredients,
            dietary_restrictions=parsed_conditions['dietary_restrictions'] if parsed_conditions['dietary_restrictions'] else None,
            cooking_time=parsed_conditions['cooking_time'],
            difficulty_level=parsed_conditions['difficulty_level'],
            cuisine_type=None,
            servings=parsed_conditions['servings'],
            flavor_profile=parsed_conditions['flavor_profile'] if parsed_conditions['flavor_profile'] else None
        )

        result = self.rag_pipeline.process_query(query)
        self.display_recipe(result, parsed_conditions)
        return result

    def display_recipe(self, result, parsed_conditions):
        """Streamlit recipe display"""
        recipe = result["recipe"]

        if ("Unable to Create Recipe" in recipe.recipe_title or 
            "Invalid" in recipe.recipe_title or 
            "No Recipe Available" in recipe.recipe_title or
            "Error" in recipe.recipe_title):
            st.error(f"❌ {recipe.recipe_title}")
            st.info(f"💡 {recipe.additional_notes}")
            return

        st.subheader(f"🍳 {recipe.recipe_title}")
        st.write(f"⏱️ **Cooking Time**: {recipe.cooking_time}")
        st.write(f"👨‍🍳 **Difficulty**: {recipe.difficulty.title()}")
        st.write(f"🍽️ **Servings**: {recipe.servings}")

        if parsed_conditions.get('dietary_restrictions'):
            st.write("🥗 **Diet**: " + ", ".join(parsed_conditions['dietary_restrictions']).title())

        if parsed_conditions.get('flavor_profile'):
            st.write(f"🌶️ **Flavor**: {parsed_conditions['flavor_profile'].title()}")

        st.markdown("### 🥕 Ingredients")
        for i, ing in enumerate(recipe.ingredients, 1):
            st.write(f"{i}. {ing}")

        st.markdown("### 📝 Instructions")
        for i, step in enumerate(recipe.instructions, 1):
            st.write(f"{i}. {step}")

        if recipe.additional_notes:
            st.markdown("### 💡 Additional Notes")
            st.write(recipe.additional_notes)


# ---------------- Streamlit UI ----------------
def main():
    st.title("🍳 Recipe Generator with RAG")
    st.write("Enter ingredients and optional conditions to get a recipe!")

    generator = RecipeGenerator()

    ingredients_input = st.text_area("📝 Enter ingredients (comma-separated)")
    conditions_input = st.text_input("⚙️ Enter conditions (optional)")

    if st.button("Generate Recipe"):
        if not ingredients_input.strip():
            st.warning("⚠️ Please enter at least one ingredient")
        else:
            ingredients = [ing.strip() for ing in ingredients_input.split(",") if ing.strip()]
            generator.search_recipes(ingredients, conditions_input)


if __name__ == "__main__":
    main()
