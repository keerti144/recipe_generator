#!/usr/bin/env python3
import os
import json
from typing import List
from dotenv import load_dotenv
import streamlit as st

from models import RecipeQuery
from rag_pipeline import RAGPipeline

load_dotenv()

class RecipeGenerator:
    def __init__(self):
        self.rag_pipeline = RAGPipeline()

        # Auto-ingest recipes.json when running in Streamlit
        recipes_file = os.path.join(os.path.dirname(__file__), "..", "data", "recipes.json")
        recipes_file = os.path.abspath(recipes_file)

        if os.path.exists(recipes_file):
            success = self.rag_pipeline.ingest_recipes(recipes_file)
            if success:
                print(f"✅ Recipes ingested from {recipes_file}")
            else:
                print("⚠️ Recipe ingestion failed.")
        else:
            print(f"⚠️ Recipes file not found at {recipes_file}")

    def ingest_data(self, recipes_file: str):
        """Ingest recipe data from JSON file"""
        if not os.path.exists(recipes_file):
            st.error(f"❌ Recipe file {recipes_file} not found!")
            return False
        
        success = self.rag_pipeline.ingest_recipes(recipes_file)
        
        if success:
            st.success("✅ Data ingestion completed successfully!")
        else:
            st.error("❌ Data ingestion failed!")
        
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
            
            # Parse servings
            import re
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

        # Debug log: show what backend actually returned
        print("🔎 DEBUG - Recipe from RAG:", result)

        # Display in Streamlit
        self.display_recipe(result)
        
        return result
    
    def display_recipe(self, result):
        """Display the generated recipe in a formatted way (Streamlit)"""
        recipe = result["recipe"]

        # Debug log cooking_time specifically
        print(f"🔎 DEBUG - Displaying Cooking Time: {recipe.cooking_time}")

        if "Unable to Create Recipe" in recipe.recipe_title or "Invalid" in recipe.recipe_title:
            st.error(f"❌ {recipe.recipe_title}")
            st.info(f"💡 {recipe.additional_notes}")
            return
        
        st.subheader(f"🍳 {recipe.recipe_title}")
        # Show cooking_time EXACTLY as backend gave it
        st.write(f"⏱️ **Cooking Time**: {recipe.cooking_time}")
        st.write(f"👨‍🍳 **Difficulty**: {recipe.difficulty.capitalize()}")
        st.write(f"🍽️ **Servings**: {recipe.servings}")
        
        st.markdown("### 🥕 Ingredients")
        for i, ingredient in enumerate(recipe.ingredients, 1):
            st.write(f"{i}. {ingredient}")
        
        st.markdown("### 📝 Instructions")
        for i, instruction in enumerate(recipe.instructions, 1):
            st.write(f"{i}. {instruction}")
        
        if recipe.additional_notes:
            st.markdown("### 💡 Additional Notes")
            st.write(recipe.additional_notes)


# ---------------- Streamlit UI ----------------
def main():
    st.title("🍳 Recipe Generator with RAG")
    st.write("Enter ingredients and optional conditions to get a recipe!")

    # Initialize generator
    generator = RecipeGenerator()
   
    # Ingredients & Conditions input
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
