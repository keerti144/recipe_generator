import sys
import os
import json
import streamlit as st

# Add project root (one level up from frontend/) to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- Try to load backend ---
backend_available = False
try:
    from backend.dummy_backend import RecipeGenerator
    generator = RecipeGenerator()
    backend_available = True
except Exception as e:
    st.warning(f"⚠️ Backend not available, using static mode. Error: {e}")

# --- Load recipes.json for fallback ---
recipes_file = os.path.join(os.path.dirname(__file__), "..", "data", "recipes.json")
recipes = []
if os.path.exists(recipes_file):
    try:
        with open(recipes_file, "r", encoding="utf-8") as f:
            recipes = json.load(f)
    except Exception as e:
        st.error(f"Error loading recipes.json: {e}")


st.title("🍳 Recipe Generator")

ingredients = st.text_input("Enter ingredients (comma-separated):")
conditions = st.text_input("Add conditions (optional, e.g., 'vegetarian under 20 mins')")

if st.button("Generate Recipe"):
    user_ingredients = [ing.strip().lower() for ing in ingredients.split(",") if ing.strip()]
    user_conditions = conditions.lower().split() if conditions else []

    if backend_available:
        try:
            with st.spinner("Generating recipe..."):
                recipe_result = generator.search_recipes(
                    user_ingredients,
                    conditions if conditions else None
                )
                recipe = recipe_result["recipe"]

            st.subheader(f"🍽️ {recipe.recipe_title}")
            st.write(f"⏱️ Time: {recipe.cooking_time}")
            st.write(f"👨‍🍳 Difficulty: {recipe.difficulty}")
            st.write(f"🍴 Servings: {recipe.servings}")

            st.markdown("### 🥕 Ingredients")
            for ing in recipe.ingredients:
                st.write(f"- {ing}")

            st.markdown("### 📝 Instructions")
            for i, step in enumerate(recipe.instructions, 1):
                st.write(f"{i}. {step}")

            if recipe.additional_notes:
                st.info(recipe.additional_notes)

        except Exception as e:
            st.error(f"Error while generating recipe: {e}")

    else:
        # --- Fallback: Search recipes.json ---
        if not recipes:
            st.error("No recipes available in fallback mode.")
        else:
            matched_recipes = []
            for recipe in recipes:
                recipe_ingredients = [i.lower() for i in recipe.get("ingredients", [])]
                ingredient_match = any(
                    any(term in ing for ing in recipe_ingredients) for term in user_ingredients
                ) if user_ingredients else True

                condition_match = all(
                    cond in (recipe.get("cuisine", "").lower() + " "
                             + recipe.get("difficulty", "").lower() + " "
                             + recipe.get("cooking_time", "").lower())
                    for cond in user_conditions
                ) if user_conditions else True

                if ingredient_match and condition_match:
                    matched_recipes.append(recipe)

            if matched_recipes:
                for recipe in matched_recipes:
                    st.subheader(f"🍽️ {recipe.get('title', 'Unknown Recipe')}")
                    st.write(f"⏱️ Time: {recipe.get('cooking_time', 'N/A')}")
                    st.write(f"👨‍🍳 Difficulty: {recipe.get('difficulty', 'N/A')}")
                    st.write(f"🍴 Servings: {recipe.get('servings', 'N/A')}")

                    st.markdown("### 🥕 Ingredients")
                    for ing in recipe.get("ingredients", []):
                        st.write(f"- {ing}")

                    st.markdown("### 📝 Instructions")
                    for i, step in enumerate(recipe.get("instructions", []), 1):
                        st.write(f"{i}. {step}")
            else:
                st.warning("❌ No matching recipe found in recipes.json")
