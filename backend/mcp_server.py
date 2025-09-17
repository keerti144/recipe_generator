#!/usr/bin/env python3
import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Recipe MCP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RecipeSearchRequest(BaseModel):
    method: str
    params: Dict[str, Any]

class WebSearchRequest(BaseModel):
    method: str
    params: Dict[str, Any]

class RecipeDetailRequest(BaseModel):
    method: str
    params: Dict[str, Any]

class MCPServer:
    def __init__(self):
        self.session = None
        # Mock data as fallback
        self.mock_recipes = [
            {
                "id": "mock_1",
                "title": "Simple Chicken Stir Fry",
                "ingredients": ["2 chicken breasts", "2 tbsp soy sauce", "1 cup mixed vegetables", "2 tbsp oil"],
                "instructions": ["Cut chicken into strips", "Heat oil in pan", "Cook chicken 5-7 minutes", "Add vegetables and soy sauce", "Stir fry 3-5 minutes"],
                "totalTime": 25,
                "image": "https://example.com/chicken-stir-fry.jpg",
                "source": "mock_database"
            },
            {
                "id": "mock_2", 
                "title": "Pasta with Tomato Sauce",
                "ingredients": ["400g pasta", "3 tomatoes", "3 cloves garlic", "3 tbsp olive oil"],
                "instructions": ["Boil pasta according to package", "Heat oil in pan", "Add minced garlic", "Add chopped tomatoes", "Combine with pasta"],
                "totalTime": 20,
                "image": "https://example.com/pasta.jpg",
                "source": "mock_database"
            },
            {
                "id": "mock_3",
                "title": "Vegetable Rice Bowl",
                "ingredients": ["2 cups rice", "1 cup mixed vegetables", "2 tbsp olive oil", "1 tsp salt"],
                "instructions": ["Cook rice", "Sauté vegetables", "Mix together", "Season to taste"],
                "totalTime": 30,
                "source": "mock_database"
            }
        ]
    
    async def create_session(self):
        """Create HTTP session"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close_session(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def get_mock_recipes(self, ingredients: List[str]) -> List[Dict[str, Any]]:
        """Return mock recipes that match ingredients"""
        filtered_recipes = []
        
        for recipe in self.mock_recipes:
            # Check if any ingredient in query matches recipe ingredients
            recipe_ingredients = [ing.lower() for ing in recipe["ingredients"]]
            query_ingredients = [ing.lower() for ing in ingredients]
            
            if any(any(q_ing in r_ing for r_ing in recipe_ingredients) for q_ing in query_ingredients):
                filtered_recipes.append(recipe)
        
        return filtered_recipes
    
    async def search_themealdb_api(self, session: aiohttp.ClientSession, 
                                  ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search TheMealDB API (free, no key required)"""
        try:
            recipes = []
            
            # Search by main ingredient (TheMealDB works best with single ingredients)
            for ingredient in ingredients[:2]:  # Limit to avoid too many calls
                # Clean ingredient name
                clean_ingredient = ingredient.lower().strip()
                
                url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={clean_ingredient}"
                
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        meals = data.get("meals")
                        
                        if meals:  # meals is None if no results
                            for meal in meals[:3]:  # Limit results per ingredient
                                # Get detailed recipe info
                                detail_url = f"https://www.themealdb.com/api/json/v1/1/lookup.php?i={meal['idMeal']}"
                                
                                async with session.get(detail_url, timeout=10) as detail_response:
                                    if detail_response.status == 200:
                                        detail_data = await detail_response.json()
                                        detailed_meal = detail_data.get("meals", [{}])[0]
                                        
                                        if detailed_meal:
                                            # Extract ingredients with measurements
                                            meal_ingredients = []
                                            for i in range(1, 21):
                                                ing = detailed_meal.get(f"strIngredient{i}")
                                                if ing and ing.strip():
                                                    measure = detailed_meal.get(f"strMeasure{i}", "")
                                                    if measure and measure.strip():
                                                        meal_ingredients.append(f"{measure.strip()} {ing.strip()}")
                                                    else:
                                                        meal_ingredients.append(ing.strip())
                                            
                                            # Split instructions into steps
                                            instructions_text = detailed_meal.get("strInstructions", "")
                                            instructions = [step.strip() for step in instructions_text.split('.') if step.strip()]
                                            
                                            recipes.append({
                                                "id": f"mealdb_{meal['idMeal']}",
                                                "title": detailed_meal.get("strMeal", "Unknown Recipe"),
                                                "ingredients": meal_ingredients,
                                                "instructions": instructions,
                                                "image": detailed_meal.get("strMealThumb"),
                                                "cuisine": detailed_meal.get("strArea", "International"),
                                                "category": detailed_meal.get("strCategory", "Main Course"),
                                                "source": "themealdb",
                                                "totalTime": 45,  # Default since TheMealDB doesn't provide timing
                                                "url": detailed_meal.get("strSource", "")
                                            })
                        
                        # Small delay between requests to be respectful
                        await asyncio.sleep(0.5)
            
            return recipes
            
        except Exception as e:
            print(f"TheMealDB API error: {e}")
            return []
    
    async def search_edamam_api(self, session: aiohttp.ClientSession, 
                              ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search Edamam API (free tier available)"""
        app_id = os.getenv("EDAMAM_APP_ID")
        app_key = os.getenv("EDAMAM_APP_KEY")
        
        if not app_id or not app_key:
            print("Edamam API credentials not found")
            return []
        
        try:
            # Create query string
            query_parts = ingredients[:3]  # Limit ingredients to avoid long URLs
            if conditions and len(conditions) < 50:  # Keep conditions reasonable
                query_parts.append(conditions)
            query = " ".join(query_parts)
            
            url = "https://api.edamam.com/api/recipes/v2"
            params = {
                "type": "public",
                "q": query,
                "app_id": app_id,
                "app_key": app_key,
                "from": 0,
                "to": 5,
                "field": ["label", "image", "url", "ingredientLines", "calories", "totalTime", "cuisineType"]
            }
            
            # Add time filter if mentioned in conditions
            if conditions and any(word in conditions.lower() for word in ["quick", "fast", "minutes", "min"]):
                params["time"] = "1-30"
            
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    recipes = []
                    
                    for hit in data.get("hits", []):
                        recipe = hit.get("recipe", {})
                        recipes.append({
                            "id": f"edamam_{recipe.get('uri', '').split('#')[1] if '#' in recipe.get('uri', '') else 'unknown'}",
                            "title": recipe.get("label", "Unknown Recipe"),
                            "image": recipe.get("image"),
                            "url": recipe.get("url"),
                            "ingredients": recipe.get("ingredientLines", []),
                            "calories": int(recipe.get("calories", 0)),
                            "totalTime": recipe.get("totalTime", 30),
                            "cuisineType": recipe.get("cuisineType", ["International"])[0],
                            "source": "edamam"
                        })
                    
                    return recipes
                else:
                    print(f"Edamam API error: {response.status}")
                    
        except Exception as e:
            print(f"Edamam API error: {e}")
        
        return []
    
    async def search_recipe_apis(self, ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search for recipes using multiple APIs with fallbacks"""
        all_results = []
        session = await self.create_session()
        
        try:
            print(f"Searching for recipes with ingredients: {ingredients}")
            
            # 1. Try TheMealDB first (always available, no key needed)
            print("Trying TheMealDB API...")
            mealdb_recipes = await self.search_themealdb_api(session, ingredients, conditions)
            if mealdb_recipes:
                all_results.extend(mealdb_recipes)
                print(f"Found {len(mealdb_recipes)} recipes from TheMealDB")
            
            # 2. Try Edamam if credentials available
            if os.getenv("EDAMAM_APP_ID") and os.getenv("EDAMAM_APP_KEY"):
                print("Trying Edamam API...")
                edamam_recipes = await self.search_edamam_api(session, ingredients, conditions)
                if edamam_recipes:
                    all_results.extend(edamam_recipes)
                    print(f"Found {len(edamam_recipes)} recipes from Edamam")
            
            # 3. If no results from APIs, use mock data
            if not all_results:
                print("No API results, using mock data...")
                mock_recipes = self.get_mock_recipes(ingredients)
                all_results.extend(mock_recipes)
                print(f"Using {len(mock_recipes)} mock recipes")
                
        except Exception as e:
            print(f"Error in search_recipe_apis: {e}")
            # Fallback to mock data
            all_results = self.get_mock_recipes(ingredients)
        
        return all_results[:8]  # Limit total results
    
    async def get_nutrition_info(self, ingredients: List[str]) -> Dict[str, Any]:
        """Get nutrition information using USDA API"""
        api_key = os.getenv("USDA_API_KEY")
        if not api_key:
            return {"error": "USDA API key not available"}
        
        session = await self.create_session()
        nutrition_data = {}
        
        try:
            for ingredient in ingredients[:3]:  # Limit to avoid rate limits
                url = "https://api.nal.usda.gov/fdc/v1/foods/search"
                params = {
                    "api_key": api_key,
                    "query": ingredient,
                    "pageSize": 1,
                    "dataType": ["Foundation", "SR Legacy"]
                }
                
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        foods = data.get("foods", [])
                        if foods:
                            food = foods[0]
                            nutrients = []
                            for nutrient in food.get("foodNutrients", [])[:8]:  # Top 8 nutrients
                                nutrients.append({
                                    "name": nutrient.get("nutrientName", "Unknown"),
                                    "amount": nutrient.get("value", 0),
                                    "unit": nutrient.get("unitName", "")
                                })
                            
                            nutrition_data[ingredient] = {
                                "description": food.get("description", "Unknown"),
                                "nutrients": nutrients
                            }
                
                # Small delay between requests
                await asyncio.sleep(0.5)
                        
        except Exception as e:
            print(f"Nutrition API error: {e}")
            return {"error": str(e)}
        
        return nutrition_data

# Initialize MCP server
mcp_server = MCPServer()

@app.on_event("startup")
async def startup_event():
    await mcp_server.create_session()

@app.on_event("shutdown")
async def shutdown_event():
    await mcp_server.close_session()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Recipe MCP Server"}

@app.post("/api/search")
async def search_recipes(request: RecipeSearchRequest):
    """Search for recipes"""
    try:
        if request.method == "search_recipes":
            params = request.params
            ingredients = params.get("ingredients", [])
            
            if not ingredients:
                raise HTTPException(status_code=400, detail="Ingredients are required")
            
            results = await mcp_server.search_recipe_apis(ingredients)
            return {"results": results}
        else:
            raise HTTPException(status_code=400, detail="Invalid method")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/web-search")
async def web_search_recipes(request: WebSearchRequest):
    """Search for recipes from web sources"""
    try:
        if request.method == "web_search_recipes":
            params = request.params
            ingredients = params.get("ingredients", [])
            conditions = params.get("conditions", "")
            
            if not ingredients:
                raise HTTPException(status_code=400, detail="Ingredients are required")
            
            results = await mcp_server.search_recipe_apis(ingredients, conditions)
            return {"recipes": results}
        else:
            raise HTTPException(status_code=400, detail="Invalid method")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/nutrition")
async def get_nutrition_info(request: RecipeSearchRequest):
    """Get nutrition information"""
    try:
        if request.method == "get_nutrition":
            params = request.params
            ingredients = params.get("ingredients", [])
            
            if not ingredients:
                raise HTTPException(status_code=400, detail="Ingredients are required")
            
            nutrition = await mcp_server.get_nutrition_info(ingredients)
            return {"nutrition": nutrition}
        else:
            raise HTTPException(status_code=400, detail="Invalid method")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_PORT", 3000))
    uvicorn.run(
        "mcp_server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        access_log=True
    )