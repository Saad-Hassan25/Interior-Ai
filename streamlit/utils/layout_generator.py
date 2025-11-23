"""
Genetic Algorithm-based Furniture Layout Generator
Optimizes furniture placement in a room using evolutionary algorithms
and generates AI-powered placement instructions.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
import io as io_module
import base64
import json
import time
import streamlit as st
from openai import OpenAI


class LayoutGenerator:
    """Handles furniture layout optimization using genetic algorithms."""
    
    def __init__(self, api_key):
        """
        Initialize the layout generator.
        
        Args:
            api_key (str): OpenRouter API key for AI optimization
        """
        self.api_key = api_key
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    
    def prepare_furniture_for_layout(self, matched_furniture):
        """
        Convert matched furniture to format expected by layout algorithm.
        
        Args:
            matched_furniture (dict): Dictionary with furniture categories and items
                Structure: {'beds': {furniture_data}, 'chairs': {furniture_data}, ...}
            
        Returns:
            list: List of furniture pieces with dimensions in feet
        """
        furniture_list = []
        
        category_mapping = {
            'beds': 'bed',
            'chairs': 'chair', 
            'sofas': 'sofa',
            'tables': 'table'
        }
        
        for category, item_data in matched_furniture.items():
            # Handle both formats: direct item or nested {'item': ...}
            if isinstance(item_data, dict):
                # Check if it's wrapped in 'item' key
                if 'item' in item_data:
                    item = item_data['item']
                else:
                    # Direct furniture data
                    item = item_data
            else:
                # Skip if not a dictionary
                continue
            
            layout_name = category_mapping.get(category.lower(), category.lower())
            
            # Get dimensions in inches from database
            length_inches = float(item.get('length', 36))
            width_inches = float(item.get('width', 24))
            
            # Convert to feet
            length_feet = length_inches / 12.0
            width_feet = width_inches / 12.0
            
            furniture_piece = {
                "name": layout_name,
                "length": length_feet,
                "width": width_feet,
                "length_inches": length_inches,
                "width_inches": width_inches,
                "db_item": item
            }
            furniture_list.append(furniture_piece)
        
        return furniture_list
    
    def generate_layout_with_custom_furniture(self, furniture_list, room_length, room_width):
        """
        Generate a single random layout with custom furniture.
        
        Args:
            furniture_list (list): List of furniture pieces
            room_length (float): Room length in feet
            room_width (float): Room width in feet
            
        Returns:
            list: Layout with randomly placed furniture
        """
        layout = []
        
        for furniture in furniture_list:
            max_x = max(0.1, room_length - furniture["length"])
            max_y = max(0.1, room_width - furniture["width"])
            
            piece = {
                "name": furniture["name"],
                "x": np.random.uniform(0, max_x),
                "y": np.random.uniform(0, max_y),
                "length": furniture["length"],
                "width": furniture["width"],
                "rotation": np.random.choice([0, 90, 180, 270]),
                "db_item": furniture.get("db_item", {})
            }
            layout.append(piece)
        
        return layout
    
    def furniture_overlap(self, f1, f2, spacing=0.5):
        """
        Check if two furniture pieces overlap with spacing.
        
        Args:
            f1 (dict): First furniture piece
            f2 (dict): Second furniture piece
            spacing (float): Minimum spacing between furniture in feet
            
        Returns:
            bool: True if furniture overlaps, False otherwise
        """
        return not (f1["x"] + f1["length"] + spacing <= f2["x"] or
                    f2["x"] + f2["length"] + spacing <= f1["x"] or
                    f1["y"] + f1["width"] + spacing <= f2["y"] or
                    f2["y"] + f2["width"] + spacing <= f1["y"])
    
    def evaluate_layout(self, layout, room_dims):
        """
        Evaluate layout quality based on multiple criteria.
        
        Args:
            layout (list): List of placed furniture
            room_dims (dict): Room dimensions (length, width)
            
        Returns:
            float: Layout score (higher is better)
        """
        score = 100.0
        room_length = room_dims["length"]
        room_width = room_dims["width"]
        
        # Penalize overlapping furniture
        for i, f1 in enumerate(layout):
            for f2 in layout[i+1:]:
                if self.furniture_overlap(f1, f2):
                    score -= 30
        
        # Penalize furniture outside room bounds
        for furniture in layout:
            if (furniture["x"] < 0 or furniture["y"] < 0 or 
                furniture["x"] + furniture["length"] > room_length or
                furniture["y"] + furniture["width"] > room_width):
                score -= 25
        
        # Bonus for furniture near walls
        wall_bonus = 0
        for furniture in layout:
            if furniture["x"] <= 0.5 or furniture["x"] + furniture["length"] >= room_length - 0.5:
                wall_bonus += 5
            if furniture["y"] <= 0.5 or furniture["y"] + furniture["width"] >= room_width - 0.5:
                wall_bonus += 5
        
        score += wall_bonus
        
        # Bonus for balanced center distribution
        center_x = room_length / 2
        center_y = room_width / 2
        
        distances = []
        for furniture in layout:
            fx = furniture["x"] + furniture["length"] / 2
            fy = furniture["y"] + furniture["width"] / 2
            dist = np.sqrt((fx - center_x)**2 + (fy - center_y)**2)
            distances.append(dist)
        
        if distances:
            avg_dist = np.mean(distances)
            if room_length * 0.2 < avg_dist < room_length * 0.4:
                score += 10
        
        return max(0, score)
    
    def crossover_layouts(self, parent1, parent2):
        """
        Create offspring by combining two parent layouts.
        
        Args:
            parent1 (list): First parent layout
            parent2 (list): Second parent layout
            
        Returns:
            list: Child layout
        """
        child = []
        for i in range(len(parent1)):
            if np.random.random() < 0.5:
                child.append(parent1[i].copy())
            else:
                child.append(parent2[i].copy())
        return child
    
    def mutate_layout(self, layout, room_length, room_width, mutation_rate=0.3):
        """
        Mutate a layout by slightly changing positions.
        
        Args:
            layout (list): Layout to mutate
            room_length (float): Room length in feet
            room_width (float): Room width in feet
            mutation_rate (float): Probability of mutation per furniture
            
        Returns:
            list: Mutated layout
        """
        mutated = []
        for furniture in layout:
            new_furniture = furniture.copy()
            
            if np.random.random() < mutation_rate:
                max_x = max(0.1, room_length - furniture["length"])
                max_y = max(0.1, room_width - furniture["width"])
                
                new_furniture["x"] = np.clip(
                    furniture["x"] + np.random.normal(0, 0.5),
                    0, max_x
                )
                new_furniture["y"] = np.clip(
                    furniture["y"] + np.random.normal(0, 0.5),
                    0, max_y
                )
            
            mutated.append(new_furniture)
        
        return mutated
    
    def generate_layouts_with_furniture(self, furniture_list, room_length, room_width, 
                                       pop_size=50, generations=50):
        """
        Generate optimal furniture layout using genetic algorithm.
        
        Args:
            furniture_list (list): List of furniture pieces
            room_length (float): Room length in feet
            room_width (float): Room width in feet
            pop_size (int): Population size for genetic algorithm
            generations (int): Number of generations to evolve
            
        Returns:
            list: Best layout found
        """
        # Initialize population
        population = []
        for _ in range(pop_size):
            layout = self.generate_layout_with_custom_furniture(furniture_list, room_length, room_width)
            population.append(layout)
        
        # Evolve population
        for gen in range(generations):
            # Evaluate fitness
            fitness_scores = [
                self.evaluate_layout(layout, {"length": room_length, "width": room_width}) 
                for layout in population
            ]
            
            # Sort by fitness
            sorted_pop = [
                layout for _, layout in sorted(zip(fitness_scores, population), key=lambda x: x[0], reverse=True)
            ]
            
            # Keep elite individuals
            elite_count = max(1, pop_size // 5)
            next_generation = sorted_pop[:elite_count].copy()
            
            # Generate new individuals
            while len(next_generation) < pop_size:
                if np.random.random() < 0.7:
                    # Crossover
                    parent_pool = sorted_pop[:pop_size//2]
                    parent_indices = np.random.choice(len(parent_pool), 2, replace=False)
                    parent1, parent2 = parent_pool[parent_indices[0]], parent_pool[parent_indices[1]]
                    child = self.crossover_layouts(parent1, parent2)
                else:
                    # Random new layout
                    child = self.generate_layout_with_custom_furniture(furniture_list, room_length, room_width)
                
                # Mutate
                child = self.mutate_layout(child, room_length, room_width)
                next_generation.append(child)
            
            population = next_generation
        
        # Return best layout
        final_fitness = [
            self.evaluate_layout(layout, {"length": room_length, "width": room_width}) 
            for layout in population
        ]
        best_layouts = [
            layout for _, layout in sorted(zip(final_fitness, population), key=lambda x: x[0], reverse=True)
        ]
        
        return best_layouts[0]
    
    def create_layout_image(self, layout, room_dims, layout_num=1):
        """
        Create a visual representation of the layout.
        
        Args:
            layout (list): Furniture layout
            room_dims (dict): Room dimensions
            layout_num (int): Layout number for title
            
        Returns:
            BytesIO: Image buffer with layout visualization
        """
        fig, ax = plt.subplots(figsize=(10, 8))
        
        room_length = room_dims["length"]
        room_width = room_dims["width"]
        
        # Set plot limits and aspect
        ax.set_xlim(-1, room_length + 1)
        ax.set_ylim(-1, room_width + 1)
        ax.set_aspect('equal')
        ax.set_title(f'Layout {layout_num} - Room: {room_length:.1f}x{room_width:.1f} ft', 
                     fontsize=14, fontweight='bold')
        
        # Draw room boundaries
        room_rect = Rectangle((0, 0), room_length, room_width, 
                             fill=False, edgecolor='black', linewidth=3)
        ax.add_patch(room_rect)
        
        # Add directional labels
        ax.text(room_length/2, room_width + 0.5, 'NORTH', ha='center', va='bottom', fontweight='bold')
        ax.text(room_length/2, -0.5, 'SOUTH', ha='center', va='top', fontweight='bold')
        ax.text(-0.5, room_width/2, 'WEST', ha='right', va='center', fontweight='bold', rotation=90)
        ax.text(room_length + 0.5, room_width/2, 'EAST', ha='left', va='center', fontweight='bold', rotation=90)
        
        # Color scheme for different furniture types
        colors = {
            'bed': '#4A90E2',
            'chair': '#F5A623', 
            'sofa': '#D0021B',
            'table': '#7ED321',
            'dresser': '#9013FE',
            'wardrobe': '#50E3C2'
        }
        
        # Draw furniture
        for furniture in layout:
            color = colors.get(furniture["name"], '#CCCCCC')
            
            # Draw furniture rectangle
            rect = FancyBboxPatch(
                (furniture["x"], furniture["y"]),
                furniture["length"], furniture["width"],
                boxstyle="round,pad=0.05",
                facecolor=color,
                edgecolor='black',
                linewidth=1.5,
                alpha=0.8
            )
            ax.add_patch(rect)
            
            # Add furniture label
            label = furniture["name"].title()
            ax.text(
                furniture["x"] + furniture["length"]/2,
                furniture["y"] + furniture["width"]/2,
                label,
                ha='center', va='center',
                fontsize=10, fontweight='bold',
                color='white',
                bbox=dict(boxstyle='round', facecolor='black', alpha=0.7, pad=0.2)
            )
            
            # Add dimensions
            dims_text = f"{furniture['length']:.1f}' x {furniture['width']:.1f}'"
            ax.text(
                furniture["x"] + furniture["length"]/2,
                furniture["y"] - 0.2,
                dims_text,
                ha='center', va='top',
                fontsize=7, color='gray'
            )
        
        # Add grid and labels
        ax.grid(True, alpha=0.3)
        ax.set_xlabel('Length (feet)', fontsize=12)
        ax.set_ylabel('Width (feet)', fontsize=12)
        
        # Save to buffer
        buffer = io_module.BytesIO()
        plt.savefig(buffer, format='png', dpi=300, bbox_inches='tight')
        buffer.seek(0)
        plt.close()
        
        return buffer
    
    def get_ai_placement_instructions(self, img_buffer, layout, room_dims, max_retries=3):
        """
        Get AI suggestions for layout optimization with JSON validation and retry logic.
        
        Args:
            img_buffer (BytesIO): Image buffer with layout visualization
            layout (list): Furniture layout
            room_dims (dict): Room dimensions
            max_retries (int): Maximum number of retry attempts
            
        Returns:
            dict: Placement instructions for each furniture piece (JSON format)
        """
        img_buffer.seek(0)
        img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
        img_data_url = f"data:image/png;base64,{img_base64}"
        
        # Build furniture description
        furniture_desc = []
        for furniture in layout:
            desc = f"- {furniture['name'].title()}: {furniture['length']:.1f} x {furniture['width']:.1f} feet"
            furniture_desc.append(desc)
        
        furniture_list_text = "\n".join(furniture_desc)
        room_info = f"Room dimensions: {room_dims['length']:.1f}x{room_dims['width']:.1f} feet"
        
        prompt = f"""You are an expert interior designer and spatial layout planner. 

You are given:
- A room layout with **North at the top** (Top/front side), **South at the bottom** (Bottom Side), **East on the right** (Right Side), and **West on the left** (Left Side).
- The following room details:
{room_info}

- A list of furniture items to place (in this exact order of placement importance : bed->sofa->chair->table). Here is the list:
{furniture_list_text}

Your goal:
Determine the **optimal placement** for each furniture item, one by one, while considering previously placed items. 
Placement decisions should optimize (initially the room is empty). Also the bed will always placed with the front side (north) wall:
1. **Traffic Flow** – clear walking paths.
2. **Functionality** – The layout given as an input may not be 100% correct. You can generate an optimal setting.
3. **Visual Balance** – symmetric and aesthetic layout.
4. **Space Utilization** – efficient use of corners and walls.
5. **Ergonomics** – comfortable distances and accessibility.
6. **Item Placement with Walls** - Bed and sofa will be always placed with walls (bed with front wall and sofa with side wall (right or left)) to maximize space.

### Output Format (MUST be valid JSON)

Respond **only** with a JSON object.  
Each value should provide one clear placement instruction using directional terms (e.g., right, left, with left wall, with right wall, near, opposite, adjacent to, with front wall, etc.) and/or relative positioning based on previously placed items.

Follow this schema exactly:
{{
  "bed": "Place the bed against the front wall.",
  "sofa": "Place the sofa with the right wall (right of bed).",
  "chair": "Place the chair with the left wall.",
  "table": "Place the table between the bed and the chair, centered in the room."
}}

IMPORTANT: Return ONLY valid JSON. Do not include any markdown formatting, explanations, or code blocks.
"""

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    st.warning(f"🔄 Retry attempt {attempt + 1}/{max_retries} for AI placement instructions...")
                
                completion = self.client.chat.completions.create(
                    model="x-ai/grok-4.1-fast:free",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": img_data_url}}
                            ]
                        }
                    ],
 
                )
                
                response_text = completion.choices[0].message.content.strip()
                
                # Clean markdown formatting if present
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                elif response_text.startswith("```"):
                    response_text = response_text.replace("```", "").strip()
                
                # Try to parse JSON
                placement_json = json.loads(response_text)
                
                # Validate that it's a dictionary with furniture placements
                if not isinstance(placement_json, dict):
                    raise ValueError("Response is not a JSON object")
                
                if len(placement_json) == 0:
                    raise ValueError("Response JSON is empty")
                
                # Success - return the parsed JSON
                if attempt > 0:
                    st.success("✅ Valid JSON response received!")
                return placement_json
                
            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    st.warning(f"⚠️ Invalid JSON response (attempt {attempt + 1}): {str(e)}")
                    time.sleep(2)  # Wait before retry
                else:
                    st.error(f"❌ Failed to get valid JSON after {max_retries} attempts")
                    st.error(f"Last response: {response_text[:200]}...")
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    st.warning(f"⚠️ Error processing response (attempt {attempt + 1}): {str(e)}")
                    time.sleep(2)
                else:
                    st.error(f"❌ Error getting AI placement instructions: {str(e)}")
                    return None
        
        return None
    
    def generate_complete_layout(self, selected_furniture, room_length, room_width, 
                                pop_size=50, generations=50):
        """
        Complete pipeline: Prepare furniture -> Generate layout -> Visualize -> Get AI instructions.
        
        Args:
            selected_furniture (dict): Dictionary of selected furniture by category
            room_length (float): Room length in feet
            room_width (float): Room width in feet
            pop_size (int): Population size for genetic algorithm
            generations (int): Number of generations
            
        Returns:
            dict: Contains layout, image_buffer, and placement_instructions
        """
        # Step 1: Prepare furniture list
        furniture_list = self.prepare_furniture_for_layout(selected_furniture)
        
        if not furniture_list:
            return {
                'success': False,
                'error': 'No furniture to place'
            }
        
        # Step 2: Generate optimal layout using genetic algorithm
        best_layout = self.generate_layouts_with_furniture(
            furniture_list, room_length, room_width, pop_size, generations
        )
        
        # Step 3: Create visualization
        room_dims = {"length": room_length, "width": room_width}
        img_buffer = self.create_layout_image(best_layout, room_dims)
        
        # Step 4: Get AI placement instructions
        placement_instructions = self.get_ai_placement_instructions(
            img_buffer, best_layout, room_dims
        )
        
        return {
            'success': True,
            'layout': best_layout,
            'image_buffer': img_buffer,
            'placement_instructions': placement_instructions,
            'room_dims': room_dims,
            'furniture_count': len(furniture_list)
        }
