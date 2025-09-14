import os
import json
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class MCPClient:
    def __init__(self):
        self.server_port = os.getenv("MCP_SERVER_PORT", "3000")
        self.base_url = f"http://localhost:{self.server_port}"
        self.session = requests.Session()
        
    def search_recipes(self, query: str, ingredients: List[str]) -> List[Dict[str, Any]]:
        """Search for recipes using MCP server"""
        try:
            payload = {
                "method": "search_recipes",
                "params": {
                    "query": query,
                    "ingredients": ingredients
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/api/search",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                print(f"MCP server error: {response.status_code}")
                return []
                
        except requests.exceptions.ConnectionError:
            print("MCP server not available, using local knowledge only")
            return []
        except Exception as e:
            print(f"Error calling MCP server: {e}")
            return []
    
    def get_recipe_details(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed recipe information"""
        try:
            payload = {
                "method": "get_recipe",
                "params": {
                    "recipe_id": recipe_id
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/api/recipe",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get("recipe")
            return None
            
        except requests.exceptions.ConnectionError:
            print("MCP server not available")
            return None
        except Exception as e:
            print(f"Error getting recipe details: {e}")
            return None
    
    def search_web_recipes(self, ingredients: List[str], conditions: str = None) -> List[Dict[str, Any]]:
        """Search for recipes from web sources"""
        try:
            payload = {
                "method": "web_search_recipes",
                "params": {
                    "ingredients": ingredients,
                    "conditions": conditions or ""
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/api/web-search",
                json=payload,
                timeout=45
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("recipes", [])
            return []
            
        except requests.exceptions.ConnectionError:
            print("MCP server not available for web search")
            return []
        except Exception as e:
            print(f"Error in web search: {e}")
            return []
    
    def health_check(self) -> bool:
        """Check if MCP server is running"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_nutrition_info(self, ingredients: List[str]) -> Dict[str, Any]:
        """Get nutrition information for ingredients"""
        try:
            payload = {
                "method": "get_nutrition",
                "params": {
                    "ingredients": ingredients
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/api/nutrition",
                json=payload,
                timeout=20
            )
            
            if response.status_code == 200:
                return response.json().get("nutrition", {})
            return {}
            
        except requests.exceptions.ConnectionError:
            print("MCP server not available for nutrition info")
            return {}
        except Exception as e:
            print(f"Error getting nutrition info: {e}")
            return {}