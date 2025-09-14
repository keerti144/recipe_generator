import os
import json
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from dotenv import load_dotenv
from models import RecipeDocument, ChunkedDocument, RecipeQuery, RecipeResponse
from qdrant_store import QdrantVectorStore
from mcp_client import MCPClient

load_dotenv()

class RAGPipeline:
    def __init__(self):
        # Initialize Azure OpenAI client
        self.azure_client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize vector store and MCP client
        self.vector_store = QdrantVectorStore()
        self.mcp_client = MCPClient()
        
        # Create collection if it doesn't exist
        self.vector_store.create_collection()
        
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        
        # Food ingredients validation
        self.common_ingredients = {
            # Proteins
            'chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 'shrimp', 'eggs', 'tofu', 'beans', 'lentils', 'chickpeas',
            # Vegetables
            'tomato', 'tomatoes', 'onion', 'onions', 'garlic', 'potato', 'potatoes', 'carrot', 'carrots', 'bell pepper', 'peppers',
            'broccoli', 'spinach', 'lettuce', 'cucumber', 'zucchini', 'eggplant', 'mushrooms', 'celery', 'corn',
            # Fruits
            'apple', 'apples', 'banana', 'bananas', 'orange', 'oranges', 'lemon', 'lemons', 'lime', 'limes', 'berries', 'strawberries',
            # Grains & Starches
            'rice', 'pasta', 'bread', 'flour', 'oats', 'quinoa', 'noodles', 'wheat', 'barley',
            # Dairy
            'milk', 'cheese', 'butter', 'yogurt', 'cream', 'mozzarella', 'parmesan', 'cheddar',
            # Pantry items
            'oil', 'olive oil', 'salt', 'pepper', 'sugar', 'honey', 'vinegar', 'soy sauce', 'herbs', 'spices',
            'basil', 'oregano', 'thyme', 'rosemary', 'paprika', 'cumin', 'ginger', 'cinnamon',
            # Nuts & Seeds
            'almonds', 'walnuts', 'peanuts', 'cashews', 'sesame seeds', 'sunflower seeds',
            # Canned/Preserved
            'canned tomatoes', 'coconut milk', 'stock', 'broth', 'olive', 'olives'
        }
    
    def validate_ingredients(self, ingredients: List[str]) -> List[str]:
        """Validate ingredients and return only valid food items"""
        valid_ingredients = []
        
        for ingredient in ingredients:
            ingredient_clean = ingredient.lower().strip()
            
            # Skip obviously non-food items
            non_food_keywords = ['human', 'person', 'people', 'man', 'woman', 'child', 'baby', 'animal', 'cat', 'dog', 
                                'plastic', 'metal', 'wood', 'paper', 'glass', 'stone', 'rock', 'dirt', 'soil',
                                'phone', 'computer', 'car', 'house', 'building', 'furniture', 'clothes', 'shoe']
            
            if any(keyword in ingredient_clean for keyword in non_food_keywords):
                continue
            
            # Check if it's a common ingredient
            if any(common in ingredient_clean or ingredient_clean in common for common in self.common_ingredients):
                valid_ingredients.append(ingredient)
            else:
                # Check if it might be a valid ingredient
                possible_food_keywords = ['sauce', 'powder', 'extract', 'leaf', 'leaves', 'seed', 'seeds', 
                                        'oil', 'vinegar', 'juice', 'fresh', 'dried', 'ground', 'chopped',
                                        'berry', 'berries', 'root', 'herb', 'spice']
                
                if any(keyword in ingredient_clean for keyword in possible_food_keywords):
                    valid_ingredients.append(ingredient)
                else:
                    # Use LLM to validate if uncertain
                    if self._is_ingredient_food_related(ingredient):
                        valid_ingredients.append(ingredient)
        
        return valid_ingredients
    
    def _is_ingredient_food_related(self, ingredient: str) -> bool:
        """Use LLM to validate if an ingredient is food-related"""
        try:
            response = self.azure_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a food expert. Respond with only 'YES' if the given item is a food ingredient that can be used in cooking, or 'NO' if it's not food or not suitable for cooking."
                    },
                    {
                        "role": "user", 
                        "content": f"Is '{ingredient}' a food ingredient suitable for cooking?"
                    }
                ],
                max_tokens=10,
                temperature=0.1
            )
            
            result = response.choices[0].message.content.strip().upper()
            return result == "YES"
            
        except Exception as e:
            return False
    
    def get_azure_embedding(self, text: str) -> List[float]:
        """Get embeddings from Azure OpenAI"""
        try:
            response = self.azure_client.embeddings.create(
                input=text,
                model=self.embedding_deployment
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error getting Azure embedding: {e}")
            # Fallback to sentence transformer
            return self.embedding_model.encode(text).tolist()
    
    def chunk_document(self, doc: RecipeDocument, chunk_size: int = 500) -> List[ChunkedDocument]:
        """Chunk a recipe document into smaller pieces"""
        chunks = []
        
        # Create chunks from different parts of the recipe
        title_chunk = ChunkedDocument(
            id=f"{doc.id}_title",
            content=f"Recipe: {doc.title}",
            metadata={
                "doc_id": doc.id,
                "type": "title",
                "cuisine": doc.cuisine,
                "difficulty": doc.difficulty,
                "cooking_time": doc.cooking_time
            }
        )
        chunks.append(title_chunk)
        
        # Ingredients chunk
        ingredients_text = f"Ingredients for {doc.title}: " + ", ".join(doc.ingredients)
        ingredients_chunk = ChunkedDocument(
            id=f"{doc.id}_ingredients",
            content=ingredients_text,
            metadata={
                "doc_id": doc.id,
                "type": "ingredients",
                "cuisine": doc.cuisine,
                "difficulty": doc.difficulty,
                "cooking_time": doc.cooking_time
            }
        )
        chunks.append(ingredients_chunk)
        
        # Instructions chunks
        instructions_text = f"Instructions for {doc.title}: " + " ".join(doc.instructions)
        if len(instructions_text) <= chunk_size:
            instructions_chunk = ChunkedDocument(
                id=f"{doc.id}_instructions",
                content=instructions_text,
                metadata={
                    "doc_id": doc.id,
                    "type": "instructions",
                    "cuisine": doc.cuisine,
                    "difficulty": doc.difficulty,
                    "cooking_time": doc.cooking_time
                }
            )
            chunks.append(instructions_chunk)
        else:
            # Split long instructions into smaller chunks
            words = instructions_text.split()
            chunk_words = chunk_size // 6  # Approximate words per chunk
            
            for i in range(0, len(words), chunk_words):
                chunk_text = " ".join(words[i:i + chunk_words])
                chunk = ChunkedDocument(
                    id=f"{doc.id}_instructions_{i}",
                    content=chunk_text,
                    metadata={
                        "doc_id": doc.id,
                        "type": "instructions",
                        "cuisine": doc.cuisine,
                        "difficulty": doc.difficulty,
                        "cooking_time": doc.cooking_time
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def ingest_recipes(self, recipes_file: str) -> bool:
        """Ingest recipes from JSON file"""
        try:
            with open(recipes_file, 'r', encoding='utf-8') as f:
                recipes_data = json.load(f)
            
            all_chunks = []
            
            for recipe_data in recipes_data:
                # Create RecipeDocument
                recipe = RecipeDocument(
                    id=recipe_data.get('id', str(len(all_chunks))),
                    title=recipe_data['title'],
                    ingredients=recipe_data['ingredients'],
                    instructions=recipe_data['instructions'],
                    cooking_time=recipe_data.get('cooking_time'),
                    difficulty=recipe_data.get('difficulty'),
                    cuisine=recipe_data.get('cuisine'),
                    servings=recipe_data.get('servings'),
                    metadata=recipe_data.get('metadata', {})
                )
                
                # Chunk the document
                chunks = self.chunk_document(recipe)
                
                # Generate embeddings for each chunk
                for chunk in chunks:
                    chunk.embedding = self.get_azure_embedding(chunk.content)
                
                all_chunks.extend(chunks)
            
            # Add to vector store
            success = self.vector_store.add_documents(all_chunks)
            if success:
                print(f"Successfully ingested {len(all_chunks)} chunks from {len(recipes_data)} recipes")
            
            return success
            
        except Exception as e:
            print(f"Error ingesting recipes: {e}")
            return False
    
    def retrieve_relevant_chunks(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant chunks from vector store"""
        try:
            query_embedding = self.get_azure_embedding(query)
            results = self.vector_store.search_similar(query_embedding, top_k)
            return results
        except Exception as e:
            print(f"Error retrieving chunks: {e}")
            return []
    
    def _parse_cooking_time_minutes(self, time_str: str) -> int:
        """Parse cooking time string to extract minutes"""
        if not time_str:
            return 30  # default
        
        time_str = time_str.lower()
        
        # Extract numbers from the string
        import re
        numbers = re.findall(r'\d+', time_str)
        
        if not numbers:
            return 30
        
        minutes = int(numbers[0])
        
        # If it says hours, convert to minutes
        if 'hour' in time_str or 'hr' in time_str:
            minutes *= 60
        
        return minutes
    
    def generate_recipe(self, query: RecipeQuery, retrieved_chunks: List[Dict[str, Any]], 
                       web_recipes: List[Dict[str, Any]] = None) -> RecipeResponse:
        """Generate recipe using Azure OpenAI with strict validation"""
        try:
            # Validate ingredients first
            valid_ingredients = self.validate_ingredients(query.ingredients)
            
            if not valid_ingredients:
                return RecipeResponse(
                    recipe_title="Unable to Create Recipe",
                    ingredients=["Please provide valid food ingredients"],
                    instructions=["No suitable ingredients available for cooking"],
                    cooking_time=query.cooking_time or "N/A",
                    difficulty=query.difficulty_level or "N/A",
                    servings=query.servings or 1,  # Ensure default to 1
                    additional_notes="Try common ingredients like chicken, rice, vegetables"
                )
            
            # Prepare context from retrieved chunks
            context_parts = []
            for chunk in retrieved_chunks:
                context_parts.append(f"Context: {chunk['content']}")
            
            # Add web recipes if available
            if web_recipes:
                for recipe in web_recipes[:3]:
                    context_parts.append(f"Web Recipe: {recipe.get('title', 'Unknown')} - {recipe.get('summary', '')}")
            
            context = "\n\n".join(context_parts)
            
            # Prepare constraints with proper defaults
            ingredients_str = ", ".join(valid_ingredients)
            target_servings = query.servings if query.servings and query.servings > 0 else 1  # Ensure default to 1
            max_cooking_time = query.cooking_time if query.cooking_time else "30 minutes"
            target_difficulty = query.difficulty_level if query.difficulty_level else "medium"
            target_cuisine = query.cuisine_type if query.cuisine_type else "any"
            dietary_restrictions = query.dietary_restrictions if query.dietary_restrictions else []
            
            # Convert cooking time for validation
            max_minutes = self._parse_cooking_time_minutes(max_cooking_time)
            
            # Create strict system prompt
            system_prompt = f"""You are a professional chef who creates ONLY realistic, practical recipes using actual food ingredients.

CRITICAL RULES - NEVER VIOLATE:
1. Use ONLY these validated food ingredients: {ingredients_str}
2. DO NOT add any ingredients not in the list above
3. DO NOT create fictional or impossible recipes
4. Servings MUST be exactly {target_servings}
5. Total cooking time MUST NOT exceed {max_cooking_time}
6. Difficulty level: {target_difficulty}
7. Create realistic portions and measurements for exactly {target_servings} serving(s)
8. Use standard cooking methods only

DIETARY RESTRICTIONS: {', '.join(dietary_restrictions) if dietary_restrictions else 'none'}
CUISINE PREFERENCE: {target_cuisine}

You MUST respond with valid JSON in this EXACT format:
{{
    "recipe_title": "Realistic Recipe Name",
    "ingredients": ["ingredient with realistic measurements for {target_servings} serving(s)"],
    "instructions": ["clear, practical step-by-step cooking instructions for {target_servings} serving(s)"],
    "cooking_time": "actual time needed (max {max_cooking_time})",
    "difficulty": "{target_difficulty}",
    "servings": {target_servings},
    "additional_notes": "practical cooking tips"
}}"""

            user_prompt = f"""Create a realistic recipe using ONLY these ingredients: {ingredients_str}

Context from database: {context}

Requirements:
- Use ONLY the ingredients listed above
- Servings: exactly {target_servings}
- Maximum time: {max_cooking_time}
- Difficulty: {target_difficulty}
- Dietary restrictions: {', '.join(dietary_restrictions) if dietary_restrictions else 'none'}

Create a practical, cookable recipe for exactly {target_servings} serving(s)."""
            
            response = self.azure_client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=1500,
                temperature=0.2  # Low temperature for consistent output
            )
            
            # Parse the response
            recipe_text = response.choices[0].message.content.strip()
            
            # Clean up JSON formatting
            if recipe_text.startswith('```json'):
                recipe_text = recipe_text[7:-3]
            elif recipe_text.startswith('```'):
                recipe_text = recipe_text[3:-3]
            
            # Extract JSON from response
            try:
                recipe_data = json.loads(recipe_text)
                
                # Enforce constraints - ensure servings is correct
                recipe_data["servings"] = target_servings  # Force the correct serving size
                
                returned_time = recipe_data.get("cooking_time", max_cooking_time)
                if self._parse_cooking_time_minutes(returned_time) > max_minutes:
                    recipe_data["cooking_time"] = max_cooking_time
                
                return RecipeResponse(
                    recipe_title=recipe_data.get("recipe_title", "Generated Recipe"),
                    ingredients=recipe_data.get("ingredients", valid_ingredients),
                    instructions=recipe_data.get("instructions", ["Instructions not generated properly"]),
                    cooking_time=recipe_data.get("cooking_time", max_cooking_time),
                    difficulty=recipe_data.get("difficulty", target_difficulty),
                    servings=target_servings,  # Ensure this is always set correctly
                    additional_notes=recipe_data.get("additional_notes")
                )
                
            except json.JSONDecodeError:
                # Fallback response
                return RecipeResponse(
                    recipe_title="Simple Recipe",
                    ingredients=[f"Use available ingredients: {', '.join(valid_ingredients)}"],
                    instructions=["Combine available ingredients using basic cooking methods"],
                    cooking_time=max_cooking_time,
                    difficulty=target_difficulty,
                    servings=target_servings,  # Ensure this is always set correctly
                    additional_notes="Generated with fallback method"
                )
                
        except Exception as e:
            print(f"Error generating recipe: {e}")
            return RecipeResponse(
                recipe_title="Error Recipe",
                ingredients=query.ingredients,
                instructions=[f"Error generating recipe: {str(e)}"],
                cooking_time=query.cooking_time or "30 minutes",
                difficulty=query.difficulty_level or "medium",
                servings=query.servings or 1,  # Ensure default to 1
                additional_notes="Error occurred during generation"
            )
    
    def process_query(self, query: RecipeQuery) -> Dict[str, Any]:
        """Process a complete query through the RAG pipeline"""
        try:
            # Ensure servings has a proper default
            if not query.servings or query.servings < 1:
                query.servings = 1
            
            # Validate ingredients first
            valid_ingredients = self.validate_ingredients(query.ingredients)
            
            if not valid_ingredients:
                return {
                    "recipe": RecipeResponse(
                        recipe_title="Unable to Create Recipe",
                        ingredients=["Please provide valid food ingredients"],
                        instructions=["No suitable ingredients available for cooking"],
                        cooking_time="N/A",
                        difficulty="N/A",
                        servings=query.servings,  # Use the corrected servings
                        additional_notes="Try common ingredients like chicken, rice, vegetables"
                    ),
                    "confidence_score": 0.0,
                    "sources_used": [],
                    "chunks_retrieved": 0,
                    "web_recipes_found": 0
                }
            
            # Create search query with valid ingredients only
            search_query = f"Recipe with ingredients: {', '.join(valid_ingredients)}"
            if query.cooking_time:
                search_query += f" cooking time {query.cooking_time}"
            if query.cuisine_type:
                search_query += f" {query.cuisine_type} cuisine"
            
            # Retrieve relevant chunks
            retrieved_chunks = self.retrieve_relevant_chunks(search_query, top_k=5)
            
            # Get web recipes via MCP if available
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
                    web_recipes = self.mcp_client.search_web_recipes(
                        valid_ingredients, 
                        conditions_str
                    )
            except Exception as e:
                web_recipes = []
            
            # Generate recipe with strict constraints
            recipe = self.generate_recipe(query, retrieved_chunks, web_recipes)
            
            # Calculate confidence score
            base_confidence = min(len(retrieved_chunks) * 0.2, 1.0)
            ingredient_confidence = len(valid_ingredients) / len(query.ingredients)
            confidence_score = base_confidence * ingredient_confidence
            
            # Prepare sources
            sources_used = []
            for chunk in retrieved_chunks:
                doc_id = chunk.get('doc_id', chunk.get('metadata', {}).get('doc_id', 'unknown'))
                sources_used.append(doc_id)
            
            if web_recipes:
                sources_used.extend([f"web:{recipe.get('source', 'unknown')}" for recipe in web_recipes[:2]])
            
            return {
                "recipe": recipe,
                "confidence_score": confidence_score,
                "sources_used": list(set(sources_used)),
                "chunks_retrieved": len(retrieved_chunks),
                "web_recipes_found": len(web_recipes)
            }
            
        except Exception as e:
            print(f"Error processing query: {e}")
            return {
                "recipe": RecipeResponse(
                    recipe_title="Error",
                    ingredients=query.ingredients,
                    instructions=[f"Error processing query: {str(e)}"],
                    cooking_time=query.cooking_time or "30 minutes",
                    difficulty=query.difficulty_level or "medium",
                    servings=query.servings or 1,  # Ensure default to 1
                ),
                "confidence_score": 0.0,
                "sources_used": [],
                "chunks_retrieved": 0,
                "web_recipes_found": 0
            }