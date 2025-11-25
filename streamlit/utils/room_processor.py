"""
Room Image Processor - Clear room and extract dimensions
Handles image upload, resizing, object removal, and dimension prediction using VLMs
"""

import os
import base64
import requests
import time
from pathlib import Path
from typing import Tuple, Optional, Dict
from PIL import Image
from io import BytesIO
import streamlit as st

# --- Configuration ---
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")

# Standard resolution for processing
STANDARD_WIDTH = 1280  # 720p width
STANDARD_HEIGHT = 720  # 720p height

# Models
VISION_EDIT_MODEL = "google/gemini-2.5-flash-image-preview"  # For object removal
VISION_CHECK_MODEL = "x-ai/grok-4.1-fast:free"  # For verification and dimension prediction

# Folders
ORIGINAL_ROOM_DIR = Path("original_room")
ORIGINAL_COPY_DIR = Path("originalcopy")
CLEAN_ROOM_DIR = Path("room_clean")


class RoomImageProcessor:
    """Process room images: resize, clear objects, and extract dimensions"""
    
    def __init__(self, api_key: str = None):
        """
        Initialize the room image processor
        
        Args:
            api_key: OpenRouter API key
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")
        
        # Create necessary directories
        ORIGINAL_ROOM_DIR.mkdir(exist_ok=True)
        ORIGINAL_COPY_DIR.mkdir(exist_ok=True)
        CLEAN_ROOM_DIR.mkdir(exist_ok=True)
    
    def resize_to_720p(self, image: Image.Image) -> Image.Image:
        """
        Resize image to standard 720p (1280x720) maintaining aspect ratio
        
        Args:
            image: PIL Image object
            
        Returns:
            Resized PIL Image object
        """
        # Calculate aspect ratio
        aspect_ratio = image.width / image.height
        target_aspect = STANDARD_WIDTH / STANDARD_HEIGHT
        
        if aspect_ratio > target_aspect:
            # Image is wider - fit to width
            new_width = STANDARD_WIDTH
            new_height = int(STANDARD_WIDTH / aspect_ratio)
        else:
            # Image is taller - fit to height
            new_height = STANDARD_HEIGHT
            new_width = int(STANDARD_HEIGHT * aspect_ratio)
        
        # Resize with high-quality resampling
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create canvas and paste centered
        canvas = Image.new('RGB', (STANDARD_WIDTH, STANDARD_HEIGHT), (255, 255, 255))
        x_offset = (STANDARD_WIDTH - new_width) // 2
        y_offset = (STANDARD_HEIGHT - new_height) // 2
        canvas.paste(resized, (x_offset, y_offset))
        
        return canvas
    
    def encode_image(self, image_path: Path) -> str:
        """Encode image to base64"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def encode_pil_image(self, image: Image.Image) -> str:
        """Encode PIL Image to base64"""
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
    
    def remove_objects_api_call(self, image_path: Path) -> Optional[Image.Image]:
        """
        Send image to Gemini model to remove all objects
        
        Args:
            image_path: Path to image file
            
        Returns:
            PIL Image with objects removed, or None on failure
        """
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        image_b64 = self.encode_image(image_path)
        
        prompt = "Remove every single object from this room. I want a completely empty room. Remove all furniture, decorations, and other items."
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    }
                ]
            }
        ]
        
        data = {
            "model": VISION_EDIT_MODEL,
            "messages": messages,
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            resp_json = response.json()
            
            assistant_msg = resp_json["choices"][0]["message"]
            img_b64 = assistant_msg["images"][0]["image_url"]["url"]
            
            # Remove data URL prefix if present
            if img_b64.startswith("data:image"):
                img_b64 = img_b64.split(",")[1]
            
            edited_img = Image.open(BytesIO(base64.b64decode(img_b64)))
            return edited_img
            
        except Exception as e:
            print(f"Error in object removal API call: {str(e)}")
            return None
    
    def check_room_cleanliness(self, image_path: Path) -> bool:
        """
        Ask VLM if the room is completely empty
        
        Args:
            image_path: Path to image file
            
        Returns:
            True if room is clean/empty, False otherwise
        """
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        image_b64 = self.encode_image(image_path)
        
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Is this room completely clean and empty without any furniture items, decorations, or objects? Only walls, floors, ceiling, windows and doors should be present. Reply with only 'yes' or 'no'."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                    }
                ]
            }
        ]
        
        data = {
            "model": VISION_CHECK_MODEL,
            "messages": messages,
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            text_response = result["choices"][0]["message"]["content"]
            
            # Handle list response
            if isinstance(text_response, list):
                text_response = "".join([c.get("text", "") for c in text_response])
            
            text_response = text_response.lower().strip()
            
            # Check for "yes" in response
            return "yes" in text_response
            
        except Exception as e:
            print(f"❌ Error in cleanliness check: {str(e)}")
            return False
    
    def predict_room_dimensions(
        self, 
        original_image_path: Path, 
        clean_image_path: Path
    ) -> Dict[str, float]:
        """
        Predict room dimensions using VLM with both original and cleaned images
        
        Args:
            original_image_path: Path to original room image
            clean_image_path: Path to cleaned/empty room image
            
        Returns:
            Dictionary with 'length' and 'width' in feet
        """
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        original_b64 = self.encode_image(original_image_path)
        clean_b64 = self.encode_image(clean_image_path)
        
        prompt = """You are an expert in analyzing room dimensions from images. 

I'm providing you with two images:
1. Original room image (with furniture)
2. Cleaned room image (empty room)

Analyze both images and estimate the room's dimensions in feet. Consider:
- Visible walls, windows, doors, and architectural features
- Perspective and depth cues
- Standard room proportions
- Any visible reference objects (before removal)

Provide your estimate in the following JSON format ONLY (no other text):
{
  "length": <number in feet>,
  "width": <number in feet>
}

Example: {"length": 15, "width": 12}

Be precise and realistic. Most residential rooms range from 10-20 feet per dimension."""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{original_b64}"}
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{clean_b64}"}
                    }
                ]
            }
        ]
        
        data = {
            "model": VISION_CHECK_MODEL,
            "messages": messages,
            "temperature": 0.3,  # Lower temperature for more consistent output
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            text_response = result["choices"][0]["message"]["content"]
            
            # Handle list response
            if isinstance(text_response, list):
                text_response = "".join([c.get("text", "") for c in text_response])
            
            # Extract JSON from response
            import json
            import re
            
            # Try to find JSON in the response
            json_match = re.search(r'\{[^}]+\}', text_response)
            if json_match:
                dimensions = json.loads(json_match.group())
                return {
                    'length': float(dimensions.get('length', 12)),
                    'width': float(dimensions.get('width', 12))
                }
            #################################
            # else:
            #     # Fallback: try to parse numbers
            #     numbers = re.findall(r'\d+\.?\d*', text_response)
            #     if len(numbers) >= 2:
            #         return {
            #             'length': float(numbers[0]),
            #             'width': float(numbers[1])
            #         }
            #     else:
            #         return {'length': 12.0, 'width': 12.0}  # Default
            
        except Exception as e:
            print(f"Error predicting dimensions: {str(e)}")
            return {'length': 12.0, 'width': 12.0}  # Default dimensions
    
    def process_uploaded_room(
        self, 
        uploaded_file,
        max_iterations: int = 3
    ) -> Dict:
        """
        Main processing pipeline for uploaded room image
        
        Args:
            uploaded_file: Streamlit uploaded file object
            max_iterations: Maximum number of object removal iterations
            
        Returns:
            Dictionary with processing results
        """
        result = {
            'success': False,
            'original_path': None,
            'clean_path': None,
            'dimensions': None,
            'iterations': 0,
            'error': None
        }
        
        try:
            # Step 1: Load and resize image to 720p
            image = Image.open(uploaded_file)
            resized_image = self.resize_to_720p(image)
            
            # Save original (resized to 720p)
            original_filename = f"room_original_{uploaded_file.name}"
            original_path = ORIGINAL_ROOM_DIR / original_filename
            resized_image.save(original_path)
            
            # Save a copy
            original_copy_path = ORIGINAL_COPY_DIR / original_filename
            resized_image.save(original_copy_path)
            
            result['original_path'] = str(original_path)
            
            # Step 2: Iterative object removal
            iteration = 1
            current_img_path = original_path
            
            while iteration <= max_iterations:
                print(f"Iteration {iteration}: Removing objects...")
                
                # Remove objects
                edited_img = self.remove_objects_api_call(current_img_path)
                
                if edited_img is None:
                    result['error'] = f"Failed at iteration {iteration}"
                    return result
                
                # Save temporarily to check cleanliness
                temp_path = CLEAN_ROOM_DIR / "temp_check.png"
                edited_img.save(temp_path)
                
                # Check if room is clean
                is_clean = self.check_room_cleanliness(temp_path)
                
                if is_clean:
                    # Room is clean! Save final result
                    final_path = CLEAN_ROOM_DIR / f"clean_{original_filename}"
                    edited_img.save(final_path)
                    result['clean_path'] = str(final_path)
                    result['iterations'] = iteration
                    
                    print(f"Room cleaned in {iteration} iteration(s)")
                    break
                else:
                    print(f"Room still has objects (iteration {iteration})")
                    # Use this as input for next iteration
                    current_img_path = temp_path
                    iteration += 1
                    time.sleep(2)  # Rate limiting
            
            if result['clean_path'] is None:
                result['error'] = f"Room still not clean after {max_iterations} iterations"
                return result
            
            # Step 3: Predict room dimensions
            print("Predicting room dimensions...")
            dimensions = self.predict_room_dimensions(
                Path(result['original_path']),
                Path(result['clean_path'])
            )
            result['dimensions'] = dimensions
            
            result['success'] = True
            print(f"Dimensions: {dimensions['length']}ft × {dimensions['width']}ft")
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            print(f"Error processing room: {str(e)}")
            return result
