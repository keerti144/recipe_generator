import os
import json
import re
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from dotenv import load_dotenv
from models import RecipeDocument, ChunkedDocument, RecipeQuery, RecipeResponse
from qdrant_store import QdrantVectorStore
from mcp_client import MCPClient

load_dotenv()

class RAGPipeline:
    def __init__(self):
        # Azure OpenAI
        self.azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )

        # Embedding
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        # Vector store + MCP
        self.vector_store = QdrantVectorStore()
        self.mcp_client = MCPClient()
        self.vector_store.create_collection()

        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

        # Pantry staples
        self.pantry_staples = {"salt", "pepper", "black pepper", "white pepper", "sugar", "oil", "olive oil", 
                             "vegetable oil", "cooking oil", "butter", "water", "garlic powder", "onion powder"}

        # Categorized ingredients for better dietary filtering
        self.vegetarian_ingredients = {
            "tomato", "onion", "garlic", "potato", "carrot", "bell pepper", "capsicum", "broccoli", 
            "spinach", "lettuce", "cucumber", "zucchini", "eggplant", "mushrooms", "celery", "corn",
            "apple", "banana", "orange", "lemon", "lime", "berries", "strawberries", "mango", "avocado",
            "rice", "pasta", "bread", "flour", "oats", "quinoa", "noodles", "wheat", "barley",
            "milk", "cheese", "butter", "yogurt", "cream", "mozzarella", "parmesan", "cheddar",
            "almonds", "walnuts", "peanuts", "cashews", "sesame seeds", "sunflower seeds",
            "tofu", "beans", "lentils", "chickpeas", "kidney beans", "black beans", "green beans",
            "paneer", "cottage cheese", "soy milk", "coconut", "coconut milk", "herbs", "basil",
            "oregano", "thyme", "rosemary", "cilantro", "parsley", "mint", "ginger", "turmeric",
            "cumin", "coriander", "chili", "chilli", "green chili", "red chili", "paprika"
        }
        
        self.non_vegetarian_ingredients = {
            "chicken", "beef", "pork", "lamb", "mutton", "fish", "salmon", "tuna", "cod", "tilapia",
            "shrimp", "prawn", "crab", "lobster", "egg", "eggs", "bacon", "ham", "sausage",
            "turkey", "duck", "goose", "venison", "rabbit", "anchovy", "sardines", "mackerel"
        }
        
        self.vegan_restricted = {
            "milk", "cheese", "butter", "yogurt", "cream", "mozzarella", "parmesan", "cheddar",
            "paneer", "cottage cheese", "egg", "eggs", "honey", "ghee", "mayonnaise"
        }

        # All common ingredients combined
        self.common_ingredients = self.vegetarian_ingredients | self.non_vegetarian_ingredients

    # ---------------- Ingredient Validation ----------------
    def validate_ingredients(self, ingredients: List[str]) -> List[str]:
        valid_ingredients = []
        for ing in ingredients:
            ing_clean = ing.lower().strip()
            # More flexible matching
            if any(common in ing_clean or ing_clean in common for common in self.common_ingredients):
                valid_ingredients.append(ing_clean)
            # Handle plurals and variations
            elif any(ing_clean.rstrip('s') in common or common in ing_clean.rstrip('s') for common in self.common_ingredients):
                valid_ingredients.append(ing_clean)
        return valid_ingredients

    # ---------------- Dietary Filtering ----------------
    def filter_ingredients_by_diet(self, ingredients: List[str], dietary_restrictions: List[str]) -> List[str]:
        if not dietary_restrictions:
            return ingredients
            
        filtered_ingredients = []
        restrictions = [d.lower() for d in dietary_restrictions]
        
        for ing in ingredients:
            ing_lower = ing.lower()
            include_ingredient = True
            
            # Vegetarian filtering - exclude non-veg
            if "vegetarian" in restrictions or "veg" in restrictions:
                if any(non_veg in ing_lower for non_veg in self.non_vegetarian_ingredients):
                    include_ingredient = False
                    continue
            
            # Non-vegetarian filtering - exclude veg proteins and emphasize meat
            if "non-vegetarian" in restrictions or "non-veg" in restrictions:
                veg_proteins = {"tofu", "beans", "lentils", "chickpeas", "paneer"}
                if any(veg_protein in ing_lower for veg_protein in veg_proteins):
                    include_ingredient = False
                    continue
            
            # Vegan filtering - exclude all animal products
            if "vegan" in restrictions:
                if (any(non_veg in ing_lower for non_veg in self.non_vegetarian_ingredients) or
                    any(restricted in ing_lower for restricted in self.vegan_restricted)):
                    include_ingredient = False
                    continue
            
            if include_ingredient:
                filtered_ingredients.append(ing)
                
        return filtered_ingredients

    # ---------------- Embeddings ----------------
    def get_azure_embedding(self, text: str) -> List[float]:
        try:
            response = self.azure_client.embeddings.create(
                input=text,
                model=self.embedding_deployment
            )
            return response.data[0].embedding
        except Exception:
            return self.embedding_model.encode(text).tolist()

    # ---------------- Chunking ----------------
    def chunk_document(self, doc: RecipeDocument, chunk_size: int = 500) -> List[ChunkedDocument]:
        chunks = []
        chunks.append(ChunkedDocument(
            id=f"{doc.id}_title",
            content=f"Recipe: {doc.title}",
            metadata={"doc_id": doc.id, "type": "title"}
        ))
        chunks.append(ChunkedDocument(
            id=f"{doc.id}_ingredients",
            content=f"Ingredients: {', '.join(doc.ingredients)}",
            metadata={"doc_id": doc.id, "type": "ingredients"}
        ))

        instructions_text = " ".join(doc.instructions)
        if len(instructions_text) <= chunk_size:
            chunks.append(ChunkedDocument(
                id=f"{doc.id}_instructions",
                content=instructions_text,
                metadata={"doc_id": doc.id, "type": "instructions"}
            ))
        else:
            words = instructions_text.split()
            chunk_words = chunk_size // 6
            for i in range(0, len(words), chunk_words):
                chunk_text = " ".join(words[i:i + chunk_words])
                chunks.append(ChunkedDocument(
                    id=f"{doc.id}_instructions_{i}",
                    content=chunk_text,
                    metadata={"doc_id": doc.id, "type": "instructions"}
                ))
        return chunks

    # ---------------- Ingest ----------------
    def ingest_recipes(self, recipes_file: str) -> bool:
        try:
            with open(recipes_file, "r", encoding="utf-8") as f:
                recipes_data = json.load(f)

            all_chunks = []
            for recipe_data in recipes_data:
                recipe = RecipeDocument(
                    id=recipe_data.get("id", str(len(all_chunks))),
                    title=recipe_data["title"],
                    ingredients=recipe_data["ingredients"],
                    instructions=recipe_data["instructions"],
                    cooking_time=recipe_data.get("cooking_time"),
                    difficulty=recipe_data.get("difficulty"),
                    cuisine=recipe_data.get("cuisine"),
                    servings=recipe_data.get("servings"),
                    metadata=recipe_data.get("metadata", {})
                )
                chunks = self.chunk_document(recipe)
                for chunk in chunks:
                    chunk.embedding = self.get_azure_embedding(chunk.content)
                all_chunks.extend(chunks)
            return self.vector_store.add_documents(all_chunks)
        except Exception as e:
            print(f"Error ingesting recipes: {e}")
            return False

    # ---------------- Retrieval ----------------
    def retrieve_relevant_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            query_embedding = self.get_azure_embedding(query)
            return self.vector_store.search_similar(query_embedding, top_k)
        except Exception as e:
            print(f"Error retrieving chunks: {e}")
            return []

    # ---------------- Parse Cooking Time ----------------
    def _parse_cooking_time_minutes(self, time_str: str) -> int:
        if not time_str:
            return 30
        
        # Extract numbers from the time string
        numbers = re.findall(r"\d+", time_str)
        if not numbers:
            return 30
            
        minutes = int(numbers[0])
        
        # Convert hours to minutes
        if "hour" in time_str.lower() or "hr" in time_str.lower():
            minutes *= 60
            
        return minutes

    # ---------------- Generate Recipe ----------------
    def generate_recipe(self, query: RecipeQuery, retrieved_chunks: List[Dict[str, Any]],
                        web_recipes: List[Dict[str, Any]] = None) -> RecipeResponse:
        try:
            # Validate and filter ingredients
            valid_ingredients = self.validate_ingredients(query.ingredients)
            if not valid_ingredients:
                return RecipeResponse(
                    recipe_title="Unable to Create Recipe",
                    ingredients=["Please provide valid ingredients"],
                    instructions=["No valid ingredients found. Try common vegetables, grains, or proteins."],
                    cooking_time=query.cooking_time or "N/A",
                    difficulty=query.difficulty_level or "N/A",
                    servings=query.servings or 1,
                    additional_notes="Provide common ingredients like chicken, rice, vegetables, etc."
                )

            # Apply dietary restrictions to filter ingredients
            filtered_ingredients = self.filter_ingredients_by_diet(valid_ingredients, query.dietary_restrictions or [])
            
            # If no ingredients left after filtering, return appropriate message
            if not filtered_ingredients:
                diet_info = ", ".join(query.dietary_restrictions) if query.dietary_restrictions else "specified dietary"
                return RecipeResponse(
                    recipe_title="No Recipe Available",
                    ingredients=["No ingredients available for specified diet"],
                    instructions=[f"No {diet_info} ingredients found in your list."],
                    cooking_time=query.cooking_time or "N/A",
                    difficulty=query.difficulty_level or "N/A",
                    servings=query.servings or 1,
                    additional_notes=f"Try adding {diet_info} ingredients to your list."
                )

            # Add pantry staples
            final_ingredients = list(set(filtered_ingredients))
            
            # Build context from retrieved chunks and web recipes
            context_parts = [f"Reference: {chunk['content']}" for chunk in retrieved_chunks[:3]]
            if web_recipes:
                for recipe in web_recipes[:2]:
                    context_parts.append(f"Example: {recipe.get('title','Unknown')} - {recipe.get('summary','')}")
            context = "\n\n".join(context_parts)

            # Extract parameters
            target_servings = query.servings or 1
            max_minutes = self._parse_cooking_time_minutes(query.cooking_time or "30 minutes")
            target_difficulty = query.difficulty_level or "medium"
            dietary_restrictions = [d.lower() for d in (query.dietary_restrictions or [])]
            flavor_profile = query.flavor_profile or ""

            # Determine realistic cooking time based on max_minutes
            realistic_cooking_time = max(10, min(max_minutes, max_minutes - 2))
            if max_minutes >= 60:
                realistic_cooking_time = max_minutes - 5  # Slightly under for longer times
            elif max_minutes >= 30:
                realistic_cooking_time = max_minutes - 3
            elif max_minutes >= 15:
                realistic_cooking_time = max_minutes - 2
            else:
                realistic_cooking_time = max(max_minutes - 1, 10)  # Minimum 10 minutes for any proper cooking

            # Create strict system prompt
            system_prompt = f"""You are a professional chef creating recipes with STRICT adherence to requirements.

MANDATORY RULES - NO EXCEPTIONS:
1. INGREDIENTS: Use ONLY these exact ingredients: {', '.join(filtered_ingredients)}
2. PANTRY STAPLES ALLOWED: {', '.join(self.pantry_staples)}
3. SERVINGS: EXACTLY {target_servings} servings - scale all quantities accordingly
4. COOKING TIME: MAXIMUM {realistic_cooking_time} minutes (be realistic, not 2-3 minutes)
5. DIFFICULTY: {target_difficulty}
6. DIETARY: {', '.join(dietary_restrictions) if dietary_restrictions else 'no restrictions'}
7. FLAVOR: {flavor_profile if flavor_profile else 'balanced'}

INGREDIENT FORMAT REQUIREMENTS:
- Include EXACT measurements: "200g chicken breast", "1/2 cup rice", "2 tbsp oil"
- Scale quantities for {target_servings} servings
- Be precise with amounts

INSTRUCTION REQUIREMENTS:
- Minimum 6 detailed steps
- Include cooking temperatures and times
- Be specific about techniques
- Include preparation details
- Realistic timing that adds up to ~{realistic_cooking_time} minutes

STRICT OUTPUT FORMAT - JSON ONLY:
{{
    "recipe_title": "Recipe Name",
    "ingredients": ["ingredient with exact measurement", ...],
    "instructions": ["detailed step 1", "detailed step 2", ...],
    "cooking_time": "{realistic_cooking_time} minutes",
    "difficulty": "{target_difficulty}",
    "servings": {target_servings},
    "additional_notes": "helpful tips and notes"
}}

ABSOLUTELY NO:
- Ingredients not in the allowed list
- Unrealistic cooking times (like 2-3 minutes)
- Vague measurements
- Wrong number of servings
- Violating dietary restrictions"""

            user_prompt = f"""Create a detailed recipe using the specified ingredients.

Requirements:
- Servings: {target_servings}
- Max time: {realistic_cooking_time} minutes
- Difficulty: {target_difficulty}
- Diet: {', '.join(dietary_restrictions) if dietary_restrictions else 'any'}
- Available ingredients: {', '.join(filtered_ingredients)}
- Flavor profile: {flavor_profile if flavor_profile else 'balanced'}

Make it detailed, practical, and delicious!"""

            response = self.azure_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.3  # Lower temperature for more consistent results
            )

            recipe_text = response.choices[0].message.content.strip()

            # Clean up JSON response
            if recipe_text.startswith("```json"):
                recipe_text = recipe_text[7:-3].strip()
            elif recipe_text.startswith("```"):
                recipe_text = recipe_text[3:-3].strip()

            try:
                recipe_data = json.loads(recipe_text)
                
                # Ensure ingredients are properly formatted
                if isinstance(recipe_data.get("ingredients"), dict):
                    recipe_data["ingredients"] = [
                        f"{k}: {v}" for k, v in recipe_data["ingredients"].items()
                    ]
                
                # Validate and enforce constraints
                recipe_data["servings"] = target_servings
                recipe_data["cooking_time"] = f"{realistic_cooking_time} minutes"
                recipe_data["difficulty"] = target_difficulty
                
            except json.JSONDecodeError:
                # Fallback recipe with proper structure
                recipe_data = {
                    "recipe_title": f"Simple {target_difficulty.title()} Recipe",
                    "ingredients": [f"Use the provided ingredients: {', '.join(filtered_ingredients[:5])}"],
                    "instructions": [
                        "Prepare all ingredients by washing and chopping as needed.",
                        "Heat oil in a pan over medium heat.",
                        "Add ingredients in order of cooking time needed.",
                        "Cook while stirring occasionally.",
                        "Season with salt and pepper to taste.",
                        "Cook until done and serve hot."
                    ],
                    "cooking_time": f"{realistic_cooking_time} minutes",
                    "difficulty": target_difficulty,
                    "servings": target_servings,
                    "additional_notes": "Recipe generated with fallback due to parsing issue."
                }

            return RecipeResponse(
                recipe_title=recipe_data.get("recipe_title", "Generated Recipe"),
                ingredients=recipe_data.get("ingredients", filtered_ingredients),
                instructions=recipe_data.get("instructions", ["Instructions not available"]),
                cooking_time=recipe_data.get("cooking_time", f"{realistic_cooking_time} minutes"),
                difficulty=recipe_data.get("difficulty", target_difficulty),
                servings=target_servings,
                additional_notes=recipe_data.get("additional_notes", "Recipe generated successfully.")
            )

        except Exception:
            return RecipeResponse(
                recipe_title="Error Generating Recipe",
                ingredients=query.ingredients,
                instructions=[f"Error occurred: {str(e)}"],
                cooking_time=query.cooking_time or "30 minutes",
                difficulty=query.difficulty_level or "medium",
                servings=query.servings or 1,
                additional_notes="An error occurred during recipe generation"
            )

    # ---------------- Process Query ----------------
    def process_query(self, query: RecipeQuery) -> Dict[str, Any]:
        try:
            # Ensure minimum servings
            if not query.servings or query.servings < 1:
                query.servings = 1

            # Normalize dietary restrictions (handle Pydantic default empty list)
            if query.dietary_restrictions and len(query.dietary_restrictions) > 0:
                normalized = []
                for d in query.dietary_restrictions:
                    d_lower = d.lower().strip()
                    if d_lower in ["veg", "vegetarian"]:
                        normalized.append("vegetarian")
                    elif d_lower in ["non-veg", "non vegetarian", "nonvegetarian", "non_veg"]:
                        normalized.append("non-vegetarian")
                    elif d_lower == "vegan":
                        normalized.append("vegan")
                    else:
                        normalized.append(d_lower)
                query.dietary_restrictions = normalized
            else:
                query.dietary_restrictions = []

            # Validate ingredients first
            valid_ingredients = self.validate_ingredients(query.ingredients)
            if not valid_ingredients:
                return {
                    "recipe": RecipeResponse(
                        recipe_title="Invalid Ingredients",
                        ingredients=["Please provide common ingredients"],
                        instructions=["No valid ingredients provided"],
                        cooking_time="N/A",
                        difficulty="N/A",
                        servings=query.servings,
                        additional_notes="Try ingredients like chicken, rice, vegetables, etc."
                    ),
                    "confidence_score": 0.0,
                    "sources_used": [],
                    "chunks_retrieved": 0,
                    "web_recipes_found": 0
                }

            # Build search query
            search_query = f"Recipe with ingredients: {', '.join(valid_ingredients)}"
            if query.cooking_time:
                search_query += f" cooking time {query.cooking_time}"
            if query.cuisine_type:
                search_query += f" {query.cuisine_type} cuisine"
            if query.dietary_restrictions:
                search_query += f" {' '.join(query.dietary_restrictions)}"

            # Retrieve relevant chunks
            retrieved_chunks = self.retrieve_relevant_chunks(search_query, top_k=5)

            # Get web recipes if available
            web_recipes = []
            try:
                if self.mcp_client.health_check():
                    conditions = []
                    if query.cooking_time:
                        conditions.append(query.cooking_time)
                    if query.difficulty_level:
                        conditions.append(query.difficulty_level)
                    if query.dietary_restrictions:
                        conditions.extend(query.dietary_restrictions)
                    conditions_str = " ".join(conditions) if conditions else None
                    web_recipes = self.mcp_client.search_web_recipes(valid_ingredients, conditions_str)
            except Exception:
                web_recipes = []

            # Generate the recipe
            recipe = self.generate_recipe(query, retrieved_chunks, web_recipes)

            # Calculate confidence score
            base_confidence = min(len(retrieved_chunks) * 0.15, 0.8)
            ingredient_confidence = len(valid_ingredients) / len(query.ingredients) if query.ingredients else 0
            web_boost = 0.1 if web_recipes else 0
            confidence_score = min(base_confidence * ingredient_confidence + web_boost, 1.0)

            # Track sources
            sources_used = []
            for chunk in retrieved_chunks:
                doc_id = chunk.get("doc_id") or chunk.get("metadata", {}).get("doc_id", "unknown")
                sources_used.append(doc_id)
            
            if web_recipes:
                sources_used.extend([f"web:{r.get('source','unknown')}" for r in web_recipes[:2]])

            return {
                "recipe": recipe,
                "confidence_score": confidence_score,
                "sources_used": list(set(sources_used)),
                "chunks_retrieved": len(retrieved_chunks),
                "web_recipes_found": len(web_recipes)
            }

        except Exception as e:
            return {
                "recipe": RecipeResponse(
                    recipe_title="Processing Error",
                    ingredients=query.ingredients or ["No ingredients"],
                    instructions=[f"Error: {str(e)}"],
                    cooking_time=query.cooking_time or "30 minutes",
                    difficulty=query.difficulty_level or "medium",
                    servings=query.servings or 1,
                    additional_notes="Error occurred during processing"
                ),
                "confidence_score": 0.0,
                "sources_used": [],
                "chunks_retrieved": 0,
                "web_recipes_found": 0
            }