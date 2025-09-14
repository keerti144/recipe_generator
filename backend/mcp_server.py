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
    
    async def search_recipe_apis(self, ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search for recipes using multiple recipe APIs"""
        results = []
        session = await self.create_session()
        
        # Example implementation - you can integrate with real recipe APIs
        try:
            # Simulated recipe API calls
            recipes = await self.search_spoonacular_api(session, ingredients, conditions)
            results.extend(recipes)
            
            recipes = await self.search_edamam_api(session, ingredients, conditions)
            results.extend(recipes)
            
        except Exception as e:
            print(f"Error searching recipe APIs: {e}")
        
        return results
    
    async def search_spoonacular_api(self, session: aiohttp.ClientSession, 
                                   ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search Spoonacular API (example implementation)"""
        # Note: You need to get actual API key from Spoonacular
        api_key = os.getenv("SPOONACULAR_API_KEY")
        if not api_key:
            return []
        
        try:
            ingredients_str = ",".join(ingredients)
            url = f"https://api.spoonacular.com/recipes/findByIngredients"
            
            params = {
                "apiKey": api_key,
                "ingredients": ingredients_str,
                "number": 5,
                "limitLicense": True,
                "ranking": 1,
                "ignorePantry": False
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        {
                            "id": recipe["id"],
                            "title": recipe["title"],
                            "image": recipe["image"],
                            "usedIngredientCount": recipe["usedIngredientCount"],
                            "missedIngredientCount": recipe["missedIngredientCount"],
                            "source": "spoonacular"
                        }
                        for recipe in data
                    ]
        except Exception as e:
            print(f"Spoonacular API error: {e}")
        
        return []
    
    async def search_edamam_api(self, session: aiohttp.ClientSession, 
                              ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search Edamam API (example implementation)"""
        # Note: You need to get actual API credentials from Edamam
        app_id = os.getenv("EDAMAM_APP_ID")
        app_key = os.getenv("EDAMAM_APP_KEY")
        
        if not app_id or not app_key:
            return []
        
        try:
            # Create query string
            query_parts = ingredients
            if conditions:
                query_parts.append(conditions)
            query = " ".join(query_parts)
            
            url = "https://api.edamam.com/search"
            params = {
                "q": query,
                "app_id": app_id,
                "app_key": app_key,
                "from": 0,
                "to": 5,
            }
            
            # Add time restrictions if specified
            if conditions and "min" in conditions.lower():
                params["time"] = "1-30"  # Under 30 minutes
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        {
                            "id": recipe["recipe"]["uri"].split("#")[1],
                            "title": recipe["recipe"]["label"],
                            "image": recipe["recipe"]["image"],
                            "url": recipe["recipe"]["url"],
                            "ingredients": recipe["recipe"]["ingredientLines"],
                            "calories": recipe["recipe"]["calories"],
                            "totalTime": recipe["recipe"].get("totalTime", 0),
                            "source": "edamam"
                        }
                        for recipe in data.get("hits", [])
                    ]
        except Exception as e:
            print(f"Edamam API error: {e}")
        
        return []
    
    async def get_recipe_details(self, recipe_id: str, source: str = "spoonacular") -> Optional[Dict[str, Any]]:
        """Get detailed recipe information"""
        session = await self.create_session()
        
        if source == "spoonacular":
            return await self.get_spoonacular_recipe_details(session, recipe_id)
        elif source == "edamam":
            return await self.get_edamam_recipe_details(session, recipe_id)
        
        return None
    
    async def get_spoonacular_recipe_details(self, session: aiohttp.ClientSession, 
                                           recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed recipe from Spoonacular"""
        api_key = os.getenv("SPOONACULAR_API_KEY")
        if not api_key:
            return None
        
        try:
            url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
            params = {
                "apiKey": api_key,
                "includeNutrition": True
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as e:
            print(f"Error getting recipe details: {e}")
        
        return None
    
    async def get_edamam_recipe_details(self, session: aiohttp.ClientSession, 
                                      recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed recipe from Edamam"""
        # Edamam details are usually included in the search results
        return None
    
    async def get_nutrition_info(self, ingredients: List[str]) -> Dict[str, Any]:
        """Get nutrition information for ingredients"""
        session = await self.create_session()
        
        # Example using USDA FoodData Central API
        try:
            nutrition_data = {}
            
            for ingredient in ingredients[:5]:  # Limit to avoid rate limits
                data = await self.search_usda_nutrition(session, ingredient)
                if data:
                    nutrition_data[ingredient] = data
            
            return nutrition_data
        except Exception as e:
            print(f"Error getting nutrition info: {e}")
            return {}
    
    async def search_usda_nutrition(self, session: aiohttp.ClientSession, 
                                  ingredient: str) -> Optional[Dict[str, Any]]:
        """Search USDA FoodData Central for nutrition info"""
        api_key = os.getenv("USDA_API_KEY")
        if not api_key:
            return None
        
        try:
            url = "https://api.nal.usda.gov/fdc/v1/foods/search"
            params = {
                "api_key": api_key,
                "query": ingredient,
                "pageSize": 1
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    foods = data.get("foods", [])
                    if foods:
                        food = foods[0]
                        return {
                            "description": food.get("description"),
                            "nutrients": food.get("foodNutrients", [])[:10]  # Top 10 nutrients
                        }
        except Exception as e:
            print(f"USDA API error: {e}")
        
        return None

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

@app.post("/api/recipe")
async def get_recipe_details(request: RecipeDetailRequest):
    """Get detailed recipe information"""
    try:
        if request.method == "get_recipe":
            params = request.params
            recipe_id = params.get("recipe_id")
            source = params.get("source", "spoonacular")
            
            if not recipe_id:
                raise HTTPException(status_code=400, detail="Recipe ID is required")
            
            recipe = await mcp_server.get_recipe_details(recipe_id, source)
            if recipe:
                return {"recipe": recipe}
            else:
                raise HTTPException(status_code=404, detail="Recipe not found")
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