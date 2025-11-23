"""
Inventory Setup Script for AI Interior Design
This script processes furniture images, generates descriptions using Nemotron,
creates embeddings using sentence transformers, and uploads everything to Supabase.

Run this script once to populate your inventory database.
"""

import os
import csv
import json
import base64
from pathlib import Path
from typing import Dict, List, Tuple
import requests
from sentence_transformers import SentenceTransformer
import streamlit as st
from supabase import create_client, Client
import time

# --- Configuration ---
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY", "")
    OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
except:
    # Fallback if running outside Streamlit
    from dotenv import load_dotenv
    load_dotenv()
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Paths
BASE_DIR = Path(__file__).parent
IMAGES_DIR = BASE_DIR / "images"
INVENTORY_CSV = BASE_DIR / "inventory" / "Inventory.csv"

# Supabase bucket name for furniture images
FURNITURE_BUCKET = "furniture-inventory"

# Embedding model
EMBEDDING_MODEL_NAME = "google/embeddinggemma-300m"

print("=" * 80)
print("🏠 AI Interior Design - Inventory Setup Script")
print("=" * 80)

# --- Initialize Supabase Client ---
def init_supabase() -> Client:
    """Initialize Supabase client with service key for admin access"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("Supabase credentials not found. Please configure in .streamlit/secrets.toml")
    
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    print("✅ Connected to Supabase")
    return supabase

# --- Load Inventory CSV ---
def load_inventory_csv() -> Dict[str, Dict]:
    """Load inventory CSV with dimensions"""
    inventory = {}
    
    # Try different encodings to handle BOM and other issues
    encodings = ['utf-8-sig', 'utf-8', 'latin-1']
    
    for encoding in encodings:
        try:
            with open(INVENTORY_CSV, 'r', encoding=encoding, newline='') as f:
                reader = csv.DictReader(f)
                
                # Read first row to check if headers are correct
                first_row = next(reader, None)
                if first_row is None:
                    continue
                
                # Check if 'name' column exists
                if 'name' not in first_row:
                    # Try to find the actual column names
                    print(f"⚠️  Column 'name' not found. Available columns: {list(first_row.keys())}")
                    continue
                
                # Process first row
                name = first_row['name'].strip()
                inventory[name] = {
                    'category': first_row['category'].strip(),
                    'length': float(first_row['length']),
                    'width': float(first_row['width'])
                }
                
                # Process remaining rows
                for row in reader:
                    name = row['name'].strip()
                    inventory[name] = {
                        'category': row['category'].strip(),
                        'length': float(row['length']),
                        'width': float(row['width'])
                    }
                
                print(f"✅ Loaded {len(inventory)} items from inventory CSV (encoding: {encoding})")
                return inventory
                
        except Exception as e:
            if encoding == encodings[-1]:  # Last encoding failed
                raise Exception(f"Failed to read CSV with all encodings. Last error: {str(e)}")
            continue
    
    raise Exception("Could not read CSV file with any encoding")

# --- Generate Description using Nemotron (Vision Model) ---
def encode_image_to_base64(image_path: Path) -> str:
    """Encode image to base64 for API"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def generate_furniture_description(image_path: Path, category: str, item_name: str) -> str:
    """
    Generate detailed furniture description using Nemotron vision model via OpenRouter
    
    The description will include:
    - Design style/theme (Modern, Traditional, Rustic, etc.)
    - Color palette
    - Materials
    - Key features
    - Suitable room types
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key not configured")
    
    # Read image as base64
    with open(image_path, 'rb') as img_file:
        image_data = base64.b64encode(img_file.read()).decode('utf-8')
    
    prompt = f"""You are an expert interior designer analyzing furniture for an e-commerce catalog. 

Analyze this {category} image and provide a detailed description that includes:

1. **Design Style/Theme**: Identify the primary design style (Modern, Contemporary, Scandinavian, Industrial, Bohemian, Minimalist, Mid-Century Modern, Farmhouse Rustic, Japanese, Mediterranean, Luxury Glam, Coastal)

2. **Color Palette**: Describe the dominant colors and any accent colors (Warm Neutral, Cool Neutral, Earth & Organic, Bold & Contrasting, Monochrome & Minimal, Pastel & Calm, Luxury & Glam, Coastal & Airy)

3. **Materials**: Identify the materials used (wood, metal, fabric, marble) and their finish/texture

4. **Key Features**: Notable design elements, patterns, shapes, or unique characteristics

5. **Suitable Spaces**: What types of rooms or spaces would this furniture work best in

6. **Atmosphere**: The mood or feeling this piece creates (elegant, cozy, sophisticated, casual, etc.)

Write a comprehensive paragraph (150-200 words) that naturally incorporates all these elements. Focus on details that would help match this furniture with a user's interior design preferences.
"""

    try:
        # Call OpenRouter API with Nemotron vision model
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "x-ai/grok-4.1-fast:free",  
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 500
            },
            timeout=60
        )
        
        response.raise_for_status()
        result = response.json()
        
        description = result['choices'][0]['message']['content'].strip()
        return description
        
    except Exception as e:
        print(f"⚠️  Error generating description for {item_name}: {str(e)}")
        # Fallback to basic description
        return f"A {category} piece featuring classic design elements suitable for various interior styles."

# --- Generate Embeddings ---
def init_embedding_model():
    """Initialize sentence transformer model for embeddings"""
    print(f"📥 Loading embedding model: {EMBEDDING_MODEL_NAME}")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print("✅ Embedding model loaded")
    return model

def generate_embedding(model: SentenceTransformer, text: str) -> List[float]:
    """Generate embedding vector for text"""
    embedding = model.encode(text, convert_to_tensor=False)
    return embedding.tolist()

# --- Upload Image to Supabase ---
def upload_image_to_supabase(supabase: Client, image_path: Path, category: str, item_name: str) -> str:
    """Upload furniture image to Supabase storage and return public URL"""
    
    # Create path in bucket: category/item_name.jpg
    storage_path = f"{category}/{item_name}.jpg"
    
    try:
        # Read image file
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Upload to Supabase storage
        supabase.storage.from_(FURNITURE_BUCKET).upload(
            storage_path,
            image_data,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
        
        # Get public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{FURNITURE_BUCKET}/{storage_path}"
        
        return public_url
        
    except Exception as e:
        print(f"⚠️  Error uploading image {item_name}: {str(e)}")
        return ""

# --- Insert into Supabase Table ---
def insert_furniture_item(supabase: Client, item_data: Dict):
    """Insert furniture item into Supabase table"""
    try:
        supabase.table('furniture_inventory').insert(item_data).execute()
        return True
    except Exception as e:
        print(f"⚠️  Error inserting item {item_data['name']}: {str(e)}")
        return False

# --- Main Processing Function ---
def process_inventory():
    """Main function to process all furniture items"""
    
    print("\n" + "=" * 80)
    print("STEP 1: Initialize Services")
    print("=" * 80)
    
    # Initialize Supabase
    supabase = init_supabase()
    
    # Load inventory CSV
    inventory_data = load_inventory_csv()
    
    # Initialize embedding model
    embedding_model = init_embedding_model()
    
    print("\n" + "=" * 80)
    print("STEP 2: Process Furniture Items")
    print("=" * 80)
    
    # Get all categories (folders)
    categories = [d.name for d in IMAGES_DIR.iterdir() if d.is_dir()]
    print(f"📁 Found categories: {', '.join(categories)}")
    
    total_items = 0
    successful_items = 0
    failed_items = []
    
    for category in categories:
        category_path = IMAGES_DIR / category
        image_files = list(category_path.glob("*.jpg")) + list(category_path.glob("*.jpeg")) + list(category_path.glob("*.png"))
        
        print(f"\n📦 Processing category: {category} ({len(image_files)} items)")
        print("-" * 80)
        
        for image_path in image_files:
            total_items += 1
            item_name = image_path.stem  # Filename without extension
            
            print(f"\n  [{total_items}] Processing: {item_name}")
            
            # Check if item exists in CSV
            if item_name not in inventory_data:
                print(f"    ⚠️  Item not found in CSV, skipping...")
                failed_items.append((item_name, "Not in CSV"))
                continue
            
            try:
                # Step 1: Generate description using Nemotron
                print(f"    🤖 Generating description with Nemotron...")
                description = generate_furniture_description(image_path, category, item_name)
                print(f"    ✅ Description generated ({len(description)} chars)")
                
                # Step 2: Generate embedding
                print(f"    🧠 Generating embedding...")
                embedding = generate_embedding(embedding_model, description)
                print(f"    ✅ Embedding generated ({len(embedding)} dimensions)")
                
                # Step 3: Upload image to Supabase
                print(f"    📤 Uploading image to Supabase...")
                image_url = upload_image_to_supabase(supabase, image_path, category, item_name)
                if not image_url:
                    raise Exception("Failed to upload image")
                print(f"    ✅ Image uploaded")
                
                # Step 4: Prepare data for insertion
                item_data = {
                    'name': item_name,
                    'category': category,
                    'description': description,
                    'image_url': image_url,
                    'length': inventory_data[item_name]['length'],
                    'width': inventory_data[item_name]['width'],
                    'embedding': embedding
                }
                
                # Step 5: Insert into database
                print(f"    💾 Inserting into database...")
                if insert_furniture_item(supabase, item_data):
                    print(f"    ✅ Successfully processed {item_name}")
                    successful_items += 1
                else:
                    raise Exception("Failed to insert into database")
                
                # Rate limiting - pause between items to avoid API limits
                time.sleep(2)
                
            except Exception as e:
                print(f"    ❌ Failed to process {item_name}: {str(e)}")
                failed_items.append((item_name, str(e)))
    
    # Final Summary
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total items: {total_items}")
    print(f"✅ Successful: {successful_items}")
    print(f"❌ Failed: {len(failed_items)}")
    
    if failed_items:
        print("\nFailed items:")
        for item_name, error in failed_items:
            print(f"  - {item_name}: {error}")
    
    print("\n" + "=" * 80)

# --- Run Script ---
if __name__ == "__main__":
    try:
        process_inventory()
    except KeyboardInterrupt:
        print("\n\n⚠️  Script interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()


