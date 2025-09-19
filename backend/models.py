from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class RecipeQuery(BaseModel):
    ingredients: List[str]
    dietary_restrictions: Optional[List[str]] = []
    cooking_time: Optional[str] = None
    difficulty_level: Optional[str] = None
    cuisine_type: Optional[str] = None
    servings: Optional[int] = None
    flavor_profile: Optional[str] = None

class RecipeDocument(BaseModel):
    id: str
    title: str
    ingredients: List[str]
    instructions: List[str]
    cooking_time: Optional[str] = None
    difficulty: Optional[str] = None
    cuisine: Optional[str] = None
    servings: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}

class ChunkedDocument(BaseModel):
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None

class RecipeResponse(BaseModel):
    recipe_title: str
    ingredients: List[str]
    instructions: List[str]
    cooking_time: str
    difficulty: str
    servings: int
    additional_notes: Optional[str] = None

class QueryRequest(BaseModel):
    query: str
    ingredients: List[str]
    conditions: Optional[str] = None

class QueryResponse(BaseModel):
    recipe: RecipeResponse
    confidence_score: float
    sources_used: List[str]