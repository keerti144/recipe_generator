# Recipe Generator - RAG + MCP Powered AI Recipe System

An intelligent recipe generation system that combines **Retrieval-Augmented Generation (RAG)** with **Model Context Protocol (MCP)** to create personalized recipes from available ingredients.

--done by **Hemashri S (23z228), Keerti Dhanyaa R (23z234) and Sruthi A (23z272)**

## How It Works

**User Experience:**
1. Input available ingredients: `chicken, rice, tomatoes`  
2. Add conditions: `under 30 mins, serves 4, spicy`
3. Get AI-generated recipe instantly

**Behind the Scenes:**
- **RAG Pipeline**: Searches pre-ingested `recipes.json` database using Qdrant vector similarity
- **MCP Integration**: Simultaneously searches web sources (TheMealDB, Edamam APIs)  
- **LLM Fusion**: Azure OpenAI combines both sources to generate the final optimized recipe

## Setup

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env with your API keys
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2023-12-01-preview
AZURE_OPENAI_DEPLOYMENT=your_gpt_deployment_name
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=your_embedding_deployment_name

QDRANT_URL=https://your-cluster.qdrant.cloud:6333
QDRANT_API_KEY=your_qdrant_api_key
QDRANT_COLLECTION_NAME=recipe_collection

MCP_SERVER_PORT=3000

# Optional API keys for enhanced web search
EDAMAM_APP_ID=your_edamam_app_id
EDAMAM_APP_KEY=your_edamam_app_key
USDA_API_KEY=your_usda_api_key
```

## Running the Application

### Streamlit Web Interface
```bash
streamlit run backend/main.py
```

Access at: `http://localhost:8501`

*Note: Data ingestion happens automatically on first run*

## Input Format

**Ingredients:** `mutton,capsicum,brinjal` (comma-separated)

**Conditions Examples:**
- **Time**: `under 15 mins`, `less than 30 minutes`
- **Difficulty**: `easy`, `medium`, `hard`
- **Servings**: `serves 4`, `for 6 people`
- **Dietary**: `vegetarian`, `vegan`, `gluten-free`
- **Combined**: `serves 2 vegetarian under 20 mins`

## Architecture

### RAG System
- **Qdrant Cloud**: Vector database for semantic recipe search
- **Azure OpenAI**: Embeddings and recipe generation
- **Auto-ingested Database**: `recipes.json` processed automatically

### MCP Integration  
- **MCP Server**: FastAPI server for external APIs
- **MCP Client**: Connects to web recipe sources
- **Web Sources**: TheMealDB, Edamam APIs

## Core Components
- `backend/main.py` - Streamlit interface + RAG pipeline
- `backend/qdrant_store.py` - Vector database operations
- `backend/mcp_server.py` - External API server
- `backend/mcp_client.py` - Web search client
- `data/recipes.json` - Recipe dataset (auto-ingested)

## Troubleshooting

**Connection Errors:**
- Ensure Qdrant Cloud credentials in `.env`
- Check Azure OpenAI API keys
- Verify internet connection for web APIs

**Streamlit Issues:**
- Try: `streamlit run --server.port 8502 backend/main.py`
- Check all dependencies installed

---

**RAG + MCP = Comprehensive Recipe Intelligence**: Local knowledge base + real-time web data = personalized recipes tailored to your ingredients and preferences.

