import streamlit as st
import json
from pathlib import Path
import requests
import streamlit as st


# --- Supabase Configuration ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
BUCKET_NAME = "interior-design-images"


# --- OpenRouter Configuration ---
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")

# --- Helper Functions ---
def load_json_file(filename):
    """Load JSON file from the streamlit directory"""
    # Go up one directory from utils/ to streamlit/
    filepath = Path(__file__).parent.parent / filename
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_image_url_from_supabase(folder, filename):
    url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{folder}/{filename}"
    return url

def display_image_grid(items, folder, selected_items, max_selections=3, item_type="theme"):
    """Display images in a grid with selection"""
    cols_per_row = 5
    cols = st.columns(cols_per_row)
    
    for idx, item in enumerate(items):
        col_idx = idx % cols_per_row
        with cols[col_idx]:
            # Get image filename
            img_filename = f"{item['name']}.jpeg"
            
            # Get image URL from Supabase
            img_url = get_image_url_from_supabase(folder.lower(), img_filename)
            
            # Display image from Supabase URL
            try:
                st.image(img_url, use_container_width=True)
            except Exception as e:
                st.warning(f"📷 {item['name']} (Image loading...)")
            
            # Checkbox for selection
            is_selected = st.checkbox(
                item['name'],
                key=f"{item_type}_{item['name']}",
                value=item['name'] in selected_items,
                disabled=len(selected_items) >= max_selections and item['name'] not in selected_items
            )
            
            # Show description in expander
            with st.expander("ℹ️ Details"):
                st.write(item['description'])

def get_selected_items_with_descriptions(selected_names, all_items):
    """Get full item details for selected items"""
    result = []
    for item in all_items:
        if item['name'] in selected_names:
            result.append({
                "name": item['name'],
                "description": item['description']
            })
    return result

def generate_room_description(user_preferences):
    """
    Generate a comprehensive room description paragraph using GPT-4 via OpenRouter.
    The description will be used for finding similar furniture items.
    """
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY_HERE":
        return {
            "success": False,
            "error": "OpenRouter API key not configured. Please add it to .streamlit/secrets.toml"
        }
    
    # Construct the prompt
    prompt = f"""You are an expert interior designer. Based on the following user preferences, create a detailed, comprehensive paragraph describing their ideal room. This description will be used to find matching furniture items, so be specific about style, colors, materials, and atmosphere.

User Preferences:
{json.dumps(user_preferences, indent=2)}

Requirements for the description:
1. MUST mention the room type ({user_preferences.get('room_type', 'room')})
2. MUST describe all selected design themes/styles with their key characteristics
3. MUST describe all selected color palettes and how they work together
4. MUST mention material preferences if any
5. Include the budget range context ({user_preferences.get('budget_range', 'medium')})
6. Consider lifestyle factors (kids, pets, entertaining, work-from-home, etc.)
7. Create a cohesive vision that blends all the selected elements
8. Focus on furniture style, materials, colors, and overall ambiance
9. Keep it as ONE comprehensive paragraph (150-250 words)
10. Write in a descriptive, professional tone suitable for furniture search

Generate the room description paragraph:"""

    try:
        # Call OpenRouter API with GPT-4
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-20b:free",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert interior designer who creates detailed room descriptions for furniture matching."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1024
            },
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        description = result['choices'][0]['message']['content'].strip()
        
        return {
            "success": True,
            "description": description,
            "tokens_used": result.get('usage', {})
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"API request failed: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating description: {str(e)}"
        }
