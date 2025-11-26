"""
Furniture Placement Module
Handles placing furniture items in the cleaned room image using AI
and refining the final result based on user preferences.
"""

import base64
import requests
import streamlit as st
from PIL import Image
from io import BytesIO
import os
from datetime import datetime


def rephrase_room_description(api_key: str, ai_room_description: str) -> str:
    """
    Rephrase the AI-generated room description to focus only on theme/design/style,
    removing furniture-specific information.
    
    Args:
        api_key (str): OpenRouter API key
        ai_room_description (str): Original AI-generated room description
        
    Returns:
        str: Rephrased description focusing on theme/design/style only
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    prompt = f"""Rephrase this room description. 

Keep the overall theme/design/style of the room. I do not need any information regarding the furniture items so remove them. The output should describe the room theme/design and style only.

Original Description:
{ai_room_description}"""

    payload = {
        "model": "openai/gpt-oss-20b:free",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.5,
        "max_tokens": 1024
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        rephrased = result['choices'][0]['message']['content'].strip()
        return rephrased
        
    except Exception as e:
        st.warning(f"Failed to rephrase description: {e}. Using original description.")
        return ai_room_description


class FurniturePlacer:
    """Handles furniture placement in room images using Gemini API."""
    
    def __init__(self, api_key):
        """
        Initialize the furniture placer.
        
        Args:
            api_key (str): OpenRouter API key
        """
        self.api_key = api_key
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "google/gemini-3-pro-image-preview"
    
    def encode_image_for_api(self, image_source):
        """
        Encode image from URL, file path, or PIL.Image object to base64.
        
        Args:
            image_source: URL string, file path string, or PIL.Image object
            
        Returns:
            str: Base64-encoded image string, or None if failed
        """
        try:
            if isinstance(image_source, Image.Image):
                # PIL Image object
                buffered = BytesIO()
                image_source.save(buffered, format="PNG")
                img_data = buffered.getvalue()
            elif isinstance(image_source, str):
                if image_source.startswith("http://") or image_source.startswith("https://"):
                    # URL
                    response = requests.get(image_source)
                    response.raise_for_status()
                    img_data = response.content
                else:
                    # File path
                    with open(image_source, "rb") as f:
                        img_data = f.read()
            else:
                return None
            
            return base64.b64encode(img_data).decode("utf-8")
        except Exception as e:
            st.error(f"Failed to encode image: {e}")
            return None
    
    def fetch_image_from_source(self, image_source):
        """
        Fetch image from URL or local path.
        
        Args:
            image_source: URL string, file path string, or PIL.Image object
            
        Returns:
            PIL.Image: Image object, or None if failed
        """
        try:
            if isinstance(image_source, Image.Image):
                return image_source
            elif image_source.startswith("http://") or image_source.startswith("https://"):
                response = requests.get(image_source)
                response.raise_for_status()
                return Image.open(BytesIO(response.content))
            elif os.path.exists(image_source):
                return Image.open(image_source)
            else:
                st.error(f"Image not found: {image_source}")
                return None
        except Exception as e:
            st.error(f"Failed to fetch image: {e}")
            return None
    
    def place_all_furniture(self, room_image_path, furniture_items, placement_instructions):
        """
        Place all furniture items in the room using a single API call.
        
        Args:
            room_image_path (str): Path to cleaned room image
            furniture_items (dict): Dictionary of selected furniture by category
            placement_instructions (dict): AI-generated placement instructions
            
        Returns:
            PIL.Image: Room with furniture placed, or None if failed
        """
        # Load room image
        room_image = self.fetch_image_from_source(room_image_path)
        if not room_image:
            return None
        
        # Encode room image
        room_b64 = self.encode_image_for_api(room_image)
        if not room_b64:
            st.error("Failed to encode room image.")
            return None
        
        # Concatenate placement instructions
        instruction_text = " ".join([
            instruction for instruction in placement_instructions.values()
        ])
        
        # Build content array with room image and furniture images
        content = [
            {"type": "text", "text": instruction_text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{room_b64}"}}
        ]
        
        # Add all furniture images
        furniture_encoded = []
        for category in ['beds', 'sofas', 'chairs', 'tables']:
            if category in furniture_items:
                item = furniture_items[category]
                image_url = item.get('image_url')
                
                if image_url:
                    furniture_b64 = self.encode_image_for_api(image_url)
                    if furniture_b64:
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{furniture_b64}"}
                        })
                        furniture_encoded.append(category)
        
        if len(furniture_encoded) == 0:
            st.error("No furniture images could be encoded.")
            return None
        
        st.info(f"🪑 Placing {len(furniture_encoded)} furniture items in the room...")
        
        # Make API call
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": content
            }],
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            resp_json = response.json()
            
            # Extract image from response
            assistant_msg = resp_json["choices"][0]["message"]
            
            if "images" in assistant_msg and len(assistant_msg["images"]) > 0:
                img_b64 = assistant_msg["images"][0]["image_url"]["url"]
                if img_b64.startswith("data:image"):
                    img_b64 = img_b64.split(",")[1]
                
                result_image = Image.open(BytesIO(base64.b64decode(img_b64)))
                return result_image
            else:
                st.error("No image returned from API.")
                return None
                
        except Exception as e:
            st.error(f"Error during furniture placement: {e}")
            if 'resp_json' in locals():
                st.error(f"API Response: {resp_json}")
            return None
    
    def refine_room_with_theme(self, room_image, ai_room_description):
        """
        Refine the room image to match the user's preferences and theme.
        
        Args:
            room_image: PIL.Image or path to room image with furniture
            ai_room_description (str): User's room description from preferences
            
        Returns:
            PIL.Image: Refined room image, or None if failed
        """
        # Encode room image
        room_b64 = self.encode_image_for_api(room_image)
        if not room_b64:
            st.error("Failed to encode room image for refinement.")
            return None
        
        st.info("Rephrasing room description to focus on theme/design/style...")
        
        # Rephrase the description to remove furniture-specific information
        rephrased_description = rephrase_room_description(self.api_key, ai_room_description)
        
        # Print the rephrased description that will be sent to the model
        st.success("✅ Rephrased Description (sent to reimagine model):")
        st.info(rephrased_description)
        print("\n" + "="*80)
        print("REPHRASED DESCRIPTION SENT TO REIMAGINE MODEL:")
        print("="*80)
        print(rephrased_description)
        print("="*80 + "\n")
        
        st.info("Refining room to match your design preferences...")
        
        # Build refinement prompt with rephrased description
        prompt = f"""Reimagine this room. The user requirements are given below. Do not change the furniture items.
User Requirements:
{rephrased_description}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{room_b64}"}}
                ]
            }],
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()
            resp_json = response.json()
            
            # Extract refined image
            assistant_msg = resp_json["choices"][0]["message"]
            
            if "images" in assistant_msg and len(assistant_msg["images"]) > 0:
                img_b64 = assistant_msg["images"][0]["image_url"]["url"]
                if img_b64.startswith("data:image"):
                    img_b64 = img_b64.split(",")[1]
                
                refined_image = Image.open(BytesIO(base64.b64decode(img_b64)))
                return refined_image
            else:
                st.error("No refined image returned from API.")
                return None
                
        except Exception as e:
            st.error(f"Error during theme refinement: {e}")
            if 'resp_json' in locals():
                st.error(f"API Response: {resp_json}")
            return None
    
    def save_result_image(self, image, output_dir, prefix="result"):
        """
        Save result image to directory with timestamp.
        
        Args:
            image (PIL.Image): Image to save
            output_dir (str): Directory to save to
            prefix (str): Filename prefix
            
        Returns:
            str: Path to saved image
        """
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(output_dir, filename)
        
        image.save(filepath)
        return filepath
