#!/usr/bin/env python3
import os
import re
from typing import List, Optional
from dotenv import load_dotenv
from backend.models import RecipeQuery
from backend.rag_pipeline import RAGPipeline

load_dotenv()

class RecipeGenerator:
    def __init__(self):
        self.rag_pipeline = RAGPipeline()

    def ingest_data(self, recipes_file: str) -> dict:
        """Ingest recipe data from JSON file"""
        if not os.path.exists(recipes_file):
            return {"success": False, "message": f"Error: Recipe file {recipes_file} not found!"}
        
        success = self.rag_pipeline.ingest_recipes(recipes_file)
        
        if success:
            return {"success": True, "message": f"Data ingestion from {recipes_file} completed successfully!"}
        else:
            return {"success": False, "message": "Data ingestion failed!"}

    def search_recipes(self, ingredients: List[str], conditions: Optional[str] = None) -> dict:
        """Search for recipes based on ingredients and conditions"""
        cooking_time = None
        difficulty_level = None
        dietary_restrictions = []
        cuisine_type = None
        servings = 1  

        if conditions:
            conditions_lower = conditions.lower()

            # Cooking time
            if "under" in conditions_lower or "less than" in conditions_lower:
                if "min" in conditions_lower:
                    for word in conditions_lower.split():
                        if word.replace("mins", "").replace("min", "").isdigit():
                            cooking_time = f"under {word.replace('mins', '').replace('min', '')} minutes"
                            break

            # Difficulty
            if "easy" in conditions_lower:
                difficulty_level = "easy"
            elif "medium" in conditions_lower:
                difficulty_level = "medium"
            elif "hard" in conditions_lower or "difficult" in conditions_lower:
                difficulty_level = "hard"

            # Dietary restrictions
            if "vegetarian" in conditions_lower:
                dietary_restrictions.append("vegetarian")
            if "vegan" in conditions_lower:
                dietary_restrictions.append("vegan")
            if "gluten-free" in conditions_lower:
                dietary_restrictions.append("gluten-free")

            # Servings parsing
            servings_found = False
            for word in conditions_lower.replace(",", " ").split():
                clean_word = word.replace("people", "").replace("person", "").replace("servings", "").replace("serves", "").replace("serving", "")
                if clean_word.isdigit():
                    servings = int(clean_word)
                    servings_found = True
                    break
            
            if not servings_found:
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

        if servings is None or servings < 1:
            servings = 1

        query = RecipeQuery(
            ingredients=ingredients,
            dietary_restrictions=dietary_restrictions if dietary_restrictions else None,
            cooking_time=cooking_time,
            difficulty_level=difficulty_level,
            cuisine_type=cuisine_type,
            servings=servings
        )
        
        result = self.rag_pipeline.process_query(query)
        return self.format_recipe(result)

    def format_recipe(self, result: dict) -> dict:
        """Return recipe in a clean dict format (instead of printing)"""
        recipe = result["recipe"]

        if "Unable to Create Recipe" in recipe.recipe_title or "Invalid" in recipe.recipe_title:
            return {
                "success": False,
                "recipe_title": recipe.recipe_title,
                "additional_notes": recipe.additional_notes
            }

        return {
            "success": True,
            "recipe_title": recipe.recipe_title,
            "cooking_time": recipe.cooking_time,
            "difficulty": recipe.difficulty,
            "servings": recipe.servings,
            "ingredients": recipe.ingredients,
            "instructions": recipe.instructions,
            "additional_notes": recipe.additional_notes,
        }
