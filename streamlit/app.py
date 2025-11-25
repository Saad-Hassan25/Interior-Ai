import streamlit as st
import json
import time
from pathlib import Path
import requests
from utils.functions import *
from utils.furniture_matcher import FurnitureMatcher, save_user_selections
from utils.room_processor import RoomImageProcessor
from utils.layout_generator import LayoutGenerator
from utils.furniture_placement import FurniturePlacer
from supabase import create_client
from PIL import Image

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Interior Design Assistant",
    page_icon="🏠",
    layout="wide"
)

# --- Load Data ---
themes_data = load_json_file('theme_descriptions.json')
colors_data = load_json_file('color_palletes_descriptions.json')

themes = themes_data['themes']
color_palettes = colors_data['color_palettes']

# --- Initialize Session State ---
if 'user_input' not in st.session_state:
    st.session_state.user_input = {
        'room_type': 'Bedroom',
        'design_styles': [],
        'color_palettes': [],
        'budget_range': 'Medium',
        'material_preferences': [],
        'lifestyle_fit': {
            'kids_count': 0,
            'kids_ages': '',
            'pets_count': 0,
            'pets_types': '',
            'entertaining_frequency': 'Occasionally',
            'work_from_home': False,
            'domestic_help': False,
            'domestic_help_count': 0,
            'watch_tv_in_bed': False,
            'like_to_cook': False
        }
    }

if 'furniture_recommendations' not in st.session_state:
    st.session_state.furniture_recommendations = None

if 'selected_furniture' not in st.session_state:
    st.session_state.selected_furniture = {}

if 'room_processed' not in st.session_state:
    st.session_state.room_processed = False

if 'room_data' not in st.session_state:
    st.session_state.room_data = None

if 'layout_generated' not in st.session_state:
    st.session_state.layout_generated = False

if 'layout_data' not in st.session_state:
    st.session_state.layout_data = None

if 'furniture_placed' not in st.session_state:
    st.session_state.furniture_placed = False

if 'placement_data' not in st.session_state:
    st.session_state.placement_data = None

if 'final_refined' not in st.session_state:
    st.session_state.final_refined = False

if 'refined_data' not in st.session_state:
    st.session_state.refined_data = None

# --- Initialize Supabase Client ---
try:
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
    SUPABASE_SERVICE_KEY = st.secrets.get("SUPABASE_SERVICE_KEY", "")
    if SUPABASE_URL and SUPABASE_SERVICE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    else:
        supabase = None
except Exception as e:
    supabase = None
    print(f"Supabase initialization failed: {e}")

# --- Main App ---
st.title("🏠 AI Interior Design Assistant")
st.markdown("### Tell us about your dream space!")
st.divider()

# --- Room Type Selection ---
st.header("Select Room Type")
st.markdown("*Choose the room you want to design*")

col1, col2 = st.columns(2)
with col1:
    bedroom_selected = st.button("Bedroom", use_container_width=True, type="primary" if st.session_state.user_input.get('room_type') == 'Bedroom' else "secondary")
with col2:
    livingroom_selected = st.button("Living Room", use_container_width=True, type="primary" if st.session_state.user_input.get('room_type') == 'Living Room' else "secondary")

# Update room type based on button clicks
if bedroom_selected:
    st.session_state.user_input['room_type'] = 'Bedroom'
    # Clear previous theme selections when switching room type
    st.session_state.user_input['design_styles'] = []
    st.rerun()
elif livingroom_selected:
    st.session_state.user_input['room_type'] = 'Living Room'
    # Clear previous theme selections when switching room type
    st.session_state.user_input['design_styles'] = []
    st.rerun()

# Display selected room type
room_type = st.session_state.user_input.get('room_type', 'Living Room')
st.success(f"✅ Selected Room: **{room_type}**")

st.divider()

# --- Design Styles/Themes Section ---
st.header("1️. Your Design Styles/Themes")
st.markdown(f"*Select up to 3 design styles for your {room_type.lower()}*")

# Determine which folder to use based on room type
if room_type == 'Bedroom':
    themes_folder = 'bedroom-themes'
elif room_type == 'Living Room':
    themes_folder = 'livingroom-themes'
else:
    themes_folder = 'themes'  # fallback

selected_themes = []
for theme in themes:
    if st.session_state.get(f"theme_{theme['name']}", False):
        selected_themes.append(theme['name'])

display_image_grid(themes, themes_folder, selected_themes, max_selections=3, item_type="theme")

# Update selected themes
selected_themes = [theme['name'] for theme in themes if st.session_state.get(f"theme_{theme['name']}", False)]
st.session_state.user_input['design_styles'] = get_selected_items_with_descriptions(selected_themes, themes)

if len(selected_themes) > 0:
    st.success(f"Selected {len(selected_themes)} theme(s): {', '.join(selected_themes)}")

st.divider()

# --- Color Palettes Section ---
st.header("2️. Your Color Palettes")
st.markdown("*Select up to 3 color palettes that appeal to you*")

selected_colors = []
for color in color_palettes:
    if st.session_state.get(f"color_{color['name']}", False):
        selected_colors.append(color['name'])

display_image_grid(color_palettes, 'Colors', selected_colors, max_selections=3, item_type="color")

# Update selected colors
selected_colors = [color['name'] for color in color_palettes if st.session_state.get(f"color_{color['name']}", False)]
st.session_state.user_input['color_palettes'] = get_selected_items_with_descriptions(selected_colors, color_palettes)

if len(selected_colors) > 0:
    st.success(f"Selected {len(selected_colors)} palette(s): {', '.join(selected_colors)}")

st.divider()

# --- Budget Range Section ---
st.header("3️. Your Budget Range")
budget = st.radio(
    "Select your budget range:",
    options=["Low", "Medium", "Premium"],
    index=1,
    horizontal=True
)
st.session_state.user_input['budget_range'] = budget

st.divider()

# --- Material Preferences Section ---
st.header("4️. Your Material Preferences")
st.markdown("*Select all materials you prefer*")

col1, col2, col3, col4 = st.columns(4)
materials = []

with col1:
    if st.checkbox("Wood", key="material_wood"):
        materials.append("Wood")
with col2:
    if st.checkbox("Marble", key="material_marble"):
        materials.append("Marble")
with col3:
    if st.checkbox("Metal", key="material_metal"):
        materials.append("Metal")
with col4:
    if st.checkbox("Fabric", key="material_fabric"):
        materials.append("Fabric")

st.session_state.user_input['material_preferences'] = materials

st.divider()

# --- Lifestyle Fit Section ---
st.header("5️. Your Lifestyle Fit")
st.markdown("*Help us understand your daily life*")

# Kids
col1, col2 = st.columns(2)
with col1:
    kids_count = st.number_input("Number of kids:", min_value=0, max_value=10, value=0, step=1)
    st.session_state.user_input['lifestyle_fit']['kids_count'] = kids_count
with col2:
    if kids_count > 0:
        kids_ages = st.text_input("Kids' ages (e.g., 3, 5, 8):", value="")
        st.session_state.user_input['lifestyle_fit']['kids_ages'] = kids_ages

# Pets
col1, col2 = st.columns(2)
with col1:
    pets_count = st.number_input("Number of pets:", min_value=0, max_value=10, value=0, step=1)
    st.session_state.user_input['lifestyle_fit']['pets_count'] = pets_count
with col2:
    if pets_count > 0:
        pets_types = st.text_input("Pet types (e.g., Dog, Cat):", value="")
        st.session_state.user_input['lifestyle_fit']['pets_types'] = pets_types

# Entertaining
entertaining = st.select_slider(
    "How often do you entertain guests?",
    options=["Never", "Rarely", "Occasionally", "Frequently", "Very Often"],
    value="Occasionally"
)
st.session_state.user_input['lifestyle_fit']['entertaining_frequency'] = entertaining

# Other preferences
col1, col2 = st.columns(2)
with col1:
    wfh = st.checkbox("Work from home?", key="wfh")
    st.session_state.user_input['lifestyle_fit']['work_from_home'] = wfh
    
    watch_tv = st.checkbox("Watch TV in bed?", key="watch_tv")
    st.session_state.user_input['lifestyle_fit']['watch_tv_in_bed'] = watch_tv

with col2:
    domestic_help = st.checkbox("Domestic help?", key="domestic_help")
    st.session_state.user_input['lifestyle_fit']['domestic_help'] = domestic_help
    
    if domestic_help:
        help_count = st.number_input("How many?", min_value=1, max_value=10, value=1, step=1)
        st.session_state.user_input['lifestyle_fit']['domestic_help_count'] = help_count
    
    cook = st.checkbox("Do you like to cook?", key="cook")
    st.session_state.user_input['lifestyle_fit']['like_to_cook'] = cook

st.divider()

# --- Submit and Export Section ---
st.header("6️. Review & Export Your Preferences")

if st.button("Generate AI Room Description", type="primary", use_container_width=True):
    # Validate minimum selections
    if len(selected_themes) == 0:
        st.error("Please select at least one design style/theme")
    elif len(selected_colors) == 0:
        st.error("Please select at least one color palette")
    else:
        # Generate AI room description
        with st.spinner("Generating comprehensive room description..."):
            result = generate_room_description(st.session_state.user_input)
        
        if result['success']:
            room_description = result['description']
            
            # Store description in session state
            st.session_state.user_input['ai_room_description'] = room_description
            st.session_state['description_generated'] = True
            
            st.success("Room description generated successfully!")
        else:
            st.error(f"Error: {result['error']}")

# Display room description if it exists
if st.session_state.user_input.get('ai_room_description'):
    st.divider()
    st.subheader("Your Room Description")
    
    room_description = st.session_state.user_input['ai_room_description']
    
    # Display the description
    st.markdown("### Room Description:")
    st.write(room_description)
    
    # Export options
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        # Download JSON with description
        json_str = json.dumps(st.session_state.user_input, indent=2)
        st.download_button(
            label="Download Complete JSON",
            data=json_str,
            file_name="interior_design_with_description.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col2:
        # Download just the description
        st.download_button(
            label="Download Description Only",
            data=room_description,
            file_name="room_description.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    # ===== FURNITURE RECOMMENDATION SECTION =====
    st.divider()
    st.header("7️. Find Matching Furniture")
    st.markdown("*We'll find furniture that matches your room description*")
    
    if supabase is None:
        st.error("Supabase not configured. Cannot fetch furniture recommendations.")
    else:
        if st.button("🔍 Find Matching Furniture", type="primary", use_container_width=True):
            with st.spinner("🔍 Searching our furniture inventory for perfect matches..."):
                try:
                    # Initialize furniture matcher
                    matcher = FurnitureMatcher(supabase)
                    matcher.load_embedding_model()
                    
                    # Get recommendations for all categories
                    recommendations = matcher.get_recommendations_for_all_categories(
                        room_description=room_description,
                        categories=['beds', 'chairs', 'sofas', 'tables'],
                        top_k=3
                    )
                    
                    # Format for display
                    formatted_recs = matcher.format_recommendations_for_display(recommendations)
                    st.session_state.furniture_recommendations = formatted_recs
                    
                    st.success("✅ Found matching furniture items!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error finding furniture: {str(e)}")
                    import traceback
                    with st.expander("🐛 Error Details"):
                        st.code(traceback.format_exc())
        
        # Display recommendations if available
        if st.session_state.furniture_recommendations:
            st.divider()
            st.subheader("Your Personalized Furniture Recommendations")
            st.markdown("*Select ONE item from each category that you like best*")
            
            categories_display = {
                'beds': ('🛏️', 'Beds'),
                'chairs': ('🪑', 'Chairs'),
                'sofas': ('🛋️', 'Sofas'),
                'tables': ('🪑', 'Tables')
            }
            
            for category, items in st.session_state.furniture_recommendations.items():
                if items:
                    icon, display_name = categories_display.get(category, ('📦', category.title()))
                    
                    st.markdown(f"### {icon} {display_name}")
                    st.markdown(f"*Top 3 {display_name.lower()} matching your style*")
                    
                    # Create columns for the 3 items
                    cols = st.columns(3)
                    
                    for idx, item in enumerate(items):
                        with cols[idx]:
                            # Display image
                            try:
                                st.image(item['image_url'], use_container_width=True)
                            except:
                                st.info(f"{item['name']}")
                            
                            # Item name and similarity score
                            st.markdown(f"**{item['name']}**")
                            st.caption(f"Match: {item['similarity']}%")
                            
                            # Description
                            with st.expander("Description"):
                                st.write(item['description'])
                            
                            # Dimensions
                            st.caption(f"{item['length']}\" × {item['width']}\"")
                            
                            # Selection button
                            button_key = f"select_{category}_{item['id']}"
                            is_selected = st.session_state.selected_furniture.get(category, {}).get('id') == item['id']
                            
                            if st.button(
                                "Selected" if is_selected else "Select This Item",
                                key=button_key,
                                type="primary" if is_selected else "secondary",
                                use_container_width=True
                            ):
                                st.session_state.selected_furniture[category] = item
                                st.rerun()
                    
                    st.divider()
            
            # Show selection summary
            if st.session_state.selected_furniture:
                st.success(f"You've selected {len(st.session_state.selected_furniture)} items")
                
                with st.expander("View Your Selections"):
                    for category, item in st.session_state.selected_furniture.items():
                        st.markdown(f"**{categories_display[category][1]}:** {item['name']}")
                
                # Save final selections button
                if len(st.session_state.selected_furniture) == 4:
                    st.divider()
                    
                    if st.button("Save Final Selections", type="primary", use_container_width=True):
                        try:
                            output_path = save_user_selections(
                                st.session_state.user_input,
                                st.session_state.selected_furniture,
                                "user_final_selections.json"
                            )
                            st.success(f"Final selections saved to: {output_path}")
                            
                            # Download button for final selections
                            final_json = json.dumps({
                                'user_preferences': st.session_state.user_input,
                                'selected_furniture': st.session_state.selected_furniture
                            }, indent=2)
                            
                            st.download_button(
                                label="Download Final Selections",
                                data=final_json,
                                file_name="final_room_design.json",
                                mime="application/json",
                                use_container_width=True
                            )
                        except Exception as e:
                            st.error(f"Error saving selections: {str(e)}")
                else:
                    st.info(f"Please select items from all 4 categories ({len(st.session_state.selected_furniture)}/4 selected)")

# ===== ROOM IMAGE UPLOAD & PROCESSING SECTION =====
if len(st.session_state.selected_furniture) == 4:
    st.divider()
    st.header("8️⃣ 📸 Upload Your Room Image")
    st.markdown("*Upload a photo of your room so we can prepare it for furniture placement*")
    
    uploaded_room = st.file_uploader(
        "Choose a room image",
        type=['jpg', 'jpeg', 'png'],
        help="Upload a photo of the room where you want to place the furniture"
    )
    
    if uploaded_room is not None:
        # Display uploaded image
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Uploaded Image")
            uploaded_image = Image.open(uploaded_room)
            st.image(uploaded_image, use_container_width=True)
            st.caption(f"Size: {uploaded_image.width} × {uploaded_image.height} pixels")
        
        # Process button
        if not st.session_state.room_processed:
            if st.button("Process Room Image", type="primary", use_container_width=True):
                with st.spinner("Processing your room image..."):
                    try:
                        # Initialize room processor
                        processor = RoomImageProcessor()
                        
                        # Process the room
                        st.info("Step 1: Resizing to 720p...")
                        time.sleep(0.5)
                        
                        st.info("Step 2: Removing furniture and objects...")
                        result = processor.process_uploaded_room(uploaded_room, max_iterations=3)
                        
                        if result['success']:
                            st.session_state.room_processed = True
                            st.session_state.room_data = result
                            st.success(f"Room processed successfully in {result['iterations']} iteration(s)!")
                            st.rerun()
                        else:
                            st.error(f"Error: {result['error']}")
                    
                    except Exception as e:
                        st.error(f"Error processing room: {str(e)}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
        
        # Display results if processed
        if st.session_state.room_processed and st.session_state.room_data:
            st.divider()
            st.subheader("Room Processing Complete!")
            
            room_data = st.session_state.room_data
            
            # Display before/after
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Original Room")
                if room_data['original_path']:
                    original_img = Image.open(room_data['original_path'])
                    st.image(original_img, use_container_width=True)
                    st.caption("Resized to 720p (1280×720)")
            
            with col2:
                st.markdown("### Cleaned Room")
                if room_data['clean_path']:
                    clean_img = Image.open(room_data['clean_path'])
                    st.image(clean_img, use_container_width=True)
                    st.caption(f"All objects removed ({room_data['iterations']} iterations)")
            
            # Display dimensions
            if room_data['dimensions']:
                st.divider()
                st.markdown("### Room Dimensions")
                
                dims = room_data['dimensions']
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Length", f"{dims['length']} ft")
                
                with col2:
                    st.metric("Width", f"{dims['width']} ft")
                
                with col3:
                    area = dims['length'] * dims['width']
                    st.metric("Area", f"{area:.1f} sq ft")
                
                st.info("Dimensions estimated based on the room images")
            
            # Next steps
            st.divider()
            st.success("Ready for furniture placement! Your room is prepared for the next step.")

# --- Step 9: Generate Room Layout ---
if st.session_state.room_processed and st.session_state.room_data:
    st.divider()
    st.header("9️. Generate Furniture Layout")
    st.markdown("*Using genetic algorithm to optimize furniture placement*")
    
    # Show room info
    room_dims = st.session_state.room_data['dimensions']
    st.info(f"Room Size: {room_dims['length']:.1f} ft × {room_dims['width']:.1f} ft")
    
    # Generate layout button
    if not st.session_state.layout_generated:
        if st.button("Generate Optimal Layout", type="primary", use_container_width=True):
            with st.spinner("Generating optimal layout using genetic algorithm..."):
                try:
                    # Get API key
                    OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
                    
                    if not OPENROUTER_API_KEY:
                        st.error("OpenRouter API key not found in secrets")
                    else:
                        # Initialize layout generator
                        layout_gen = LayoutGenerator(OPENROUTER_API_KEY)
                        
                        # Generate layout
                        st.info("🧬 Running genetic algorithm (50 generations, 50 population)...")
                        result = layout_gen.generate_complete_layout(
                            selected_furniture=st.session_state.selected_furniture,
                            room_length=room_dims['length'],
                            room_width=room_dims['width'],
                            pop_size=50,
                            generations=50
                        )
                        
                        if result['success']:
                            st.session_state.layout_data = result
                            st.session_state.layout_generated = True
                            st.success("Layout generated successfully!")
                            st.rerun()
                        else:
                            st.error(f"Layout generation failed: {result.get('error', 'Unknown error')}")
                
                except Exception as e:
                    st.error(f"Error generating layout: {str(e)}")
    
    # Display layout if generated
    if st.session_state.layout_generated and st.session_state.layout_data:
        layout_data = st.session_state.layout_data
        
        st.success(f"Layout generated with {layout_data['furniture_count']} furniture pieces")
        
        # # Display layout visualization
        # st.subheader("Optimized Layout")
        
        # # Show the layout image
        # layout_img = layout_data['image_buffer']
        # layout_img.seek(0)
        # st.image(layout_img, caption="Generated Room Layout", use_container_width=True)
        
        # Display AI placement instructions
        st.subheader("AI Placement Instructions")
        
        placement_instructions = layout_data.get('placement_instructions')
        
        if placement_instructions:
            st.success("AI-optimized placement instructions generated")
            
            # Display instructions in a nice format
            for furniture_name, instruction in placement_instructions.items():
                with st.expander(f" {furniture_name.title()}", expanded=True):
                    st.markdown(f"**Instruction:** {instruction}")
                    
                    # Find the furniture details from layout
                    furniture_details = next(
                        (item for item in layout_data['layout'] if item['name'] == furniture_name),
                        None
                    )
                    
                    if furniture_details:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Length", f"{furniture_details['length']:.1f} ft")
                        with col2:
                            st.metric("Width", f"{furniture_details['width']:.1f} ft")
                        # with col3:
                        #     st.metric("Position", f"({furniture_details['x']:.1f}, {furniture_details['y']:.1f})")
            
            # Export placement instructions
            st.divider()
            placement_json = json.dumps(placement_instructions, indent=2)
            st.download_button(
                label="Download Placement Instructions",
                data=placement_json,
                file_name="furniture_placement_instructions.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.warning("AI placement instructions not available")
        
        # Layout statistics
        st.divider()
        st.subheader("Layout Statistics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Room Area", f"{room_dims['length'] * room_dims['width']:.1f} sq ft")
        
        with col2:
            total_furniture_area = sum(
                item['length'] * item['width'] 
                for item in layout_data['layout']
            )
            st.metric("Furniture Area", f"{total_furniture_area:.1f} sq ft")
        
        with col3:
            space_utilization = (total_furniture_area / (room_dims['length'] * room_dims['width'])) * 100
            st.metric("Space Utilization", f"{space_utilization:.1f}%")

# --- Step 10: Place Furniture in Room ---
if st.session_state.layout_generated and st.session_state.layout_data:
    st.divider()
    st.header("10. Place Furniture in Room")
    st.markdown("*Using AI to place selected furniture items in the cleaned room*")
    
    layout_data = st.session_state.layout_data
    placement_instructions = layout_data.get('placement_instructions')
    
    if not placement_instructions:
        st.warning("No placement instructions available. Please regenerate the layout.")
    else:
        # Show placement instructions summary
        st.info(f"Placing {len(placement_instructions)} furniture items based on AI instructions")
        
        # Display concatenated instructions
        with st.expander("View Placement Instructions", expanded=False):
            concatenated = " ".join([instruction for instruction in placement_instructions.values()])
            st.markdown(f"**Instructions:** {concatenated}")
        
        # Place furniture button
        if not st.session_state.furniture_placed:
            if st.button("Place Furniture in Room", type="primary", use_container_width=True):
                with st.spinner("Placing furniture in the room..."):
                    try:
                        # Get API key
                        OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
                        
                        if not OPENROUTER_API_KEY:
                            st.error("OpenRouter API key not found in secrets")
                        else:
                            # Initialize furniture placer
                            placer = FurniturePlacer(OPENROUTER_API_KEY)
                            
                            # Get cleaned room image path
                            room_data = st.session_state.room_data
                            clean_room_path = room_data['clean_path']
                            
                            # Place all furniture
                            result_image = placer.place_all_furniture(
                                room_image_path=clean_room_path,
                                furniture_items=st.session_state.selected_furniture,
                                placement_instructions=placement_instructions
                            )
                            
                            if result_image:
                                # Save the result
                                output_dir = Path(__file__).parent / "furnished_room"
                                result_path = placer.save_result_image(
                                    result_image, 
                                    str(output_dir), 
                                    prefix="furnished"
                                )
                                
                                # Store in session state
                                st.session_state.placement_data = {
                                    'image': result_image,
                                    'path': result_path
                                }
                                st.session_state.furniture_placed = True
                                
                                st.success("Furniture placed successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to place furniture")
                    
                    except Exception as e:
                        st.error(f"Error placing furniture: {str(e)}")
        
        # Display placed furniture result
        if st.session_state.furniture_placed and st.session_state.placement_data:
            st.success("Furniture has been placed in the room!")
            
            placement_data = st.session_state.placement_data
            
            # Display before/after comparison
            st.subheader("Before & After")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Empty Room**")
                room_data = st.session_state.room_data
                clean_room = Image.open(room_data['clean_path'])
                st.image(clean_room, use_container_width=True)
            
            with col2:
                st.markdown("**Furnished Room**")
                st.image(placement_data['image'], use_container_width=True)
            
            # Download button
            st.divider()
            st.download_button(
                label="Download Furnished Room",
                data=open(placement_data['path'], 'rb').read(),
                file_name="furnished_room.png",
                mime="image/png",
                use_container_width=True
            )

# --- Step 11: Refine with Theme ---
if st.session_state.furniture_placed and st.session_state.placement_data:
    st.divider()
    st.header("1️1. Refine with Your Design Theme")
    st.markdown("*Apply your design preferences to create the final polished look*")
    
    # Show user's room description
    ai_description = st.session_state.user_input.get('ai_room_description', '')
    
    if not ai_description:
        st.warning(" No room description found. Skipping theme refinement.")
    else:
        with st.expander("Your Design Vision", expanded=False):
            st.markdown(ai_description)
        
        # Refine button
        if not st.session_state.final_refined:
            if st.button("Apply Design Theme", type="primary", use_container_width=True):
                with st.spinner("Refining room with your design theme..."):
                    try:
                        # Get API key
                        OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
                        
                        if not OPENROUTER_API_KEY:
                            st.error("OpenRouter API key not found in secrets")
                        else:
                            # Initialize furniture placer
                            placer = FurniturePlacer(OPENROUTER_API_KEY)
                            
                            # Refine the room
                            placement_data = st.session_state.placement_data
                            refined_image = placer.refine_room_with_theme(
                                room_image=placement_data['image'],
                                ai_room_description=ai_description
                            )
                            
                            if refined_image:
                                # Save the refined result
                                output_dir = Path(__file__).parent / "final_room"
                                refined_path = placer.save_result_image(
                                    refined_image, 
                                    str(output_dir), 
                                    prefix="final_refined"
                                )
                                
                                # Store in session state
                                st.session_state.refined_data = {
                                    'image': refined_image,
                                    'path': refined_path
                                }
                                st.session_state.final_refined = True
                                
                                st.success("Room refined successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to refine room")
                    
                    except Exception as e:
                        st.error(f"Error refining room: {str(e)}")
        
        # Display refined result
        if st.session_state.final_refined and st.session_state.refined_data:
            st.success("Your final design is ready!")
            
            refined_data = st.session_state.refined_data
            
            # Display progression: Empty → Furnished → Refined
            st.subheader("Design Progression")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**1️. Empty Room**")
                room_data = st.session_state.room_data
                clean_room = Image.open(room_data['clean_path'])
                st.image(clean_room, use_container_width=True)
            
            with col2:
                st.markdown("**2️. Furnished**")
                placement_data = st.session_state.placement_data
                st.image(placement_data['image'], use_container_width=True)
            
            with col3:
                st.markdown("**3️. Final Design ✨**")
                st.image(refined_data['image'], use_container_width=True)
            
            # Final result in full width
            st.divider()
            st.subheader("Your Final Interior Design")
            st.image(refined_data['image'], use_container_width=True)
            
            # Download button
            st.download_button(
                label="Download Final Design",
                data=open(refined_data['path'], 'rb').read(),
                file_name="final_interior_design.png",
                mime="image/png",
                use_container_width=True
            )

# --- Save Complete Project ---
if st.session_state.room_processed and st.session_state.room_data:
    st.divider()
    
    if st.session_state.final_refined:
        st.success("All steps completed! Your final design is ready. Save your complete project below.")
    elif st.session_state.furniture_placed:
        st.info("You can save now, or continue to refine with your design theme.")
    elif st.session_state.layout_generated:
        st.info("You can save now, or continue to place furniture in the room.")
    else:
        st.info("Generate the layout first, then continue to furniture placement.")
    
    # Save complete data
    if st.button("Save Complete Project", type="primary", use_container_width=True):
                try:
                    room_data = st.session_state.room_data
                    
                    complete_data = {
                        'user_preferences': st.session_state.user_input,
                        'selected_furniture': st.session_state.selected_furniture,
                        'room_data': {
                            'original_image': room_data['original_path'],
                            'clean_image': room_data['clean_path'],
                            'dimensions': room_data['dimensions'],
                            'iterations': room_data['iterations']
                        }
                    }
                    
                    # Add layout data if available
                    if st.session_state.layout_generated and st.session_state.layout_data:
                        layout_data = st.session_state.layout_data
                        complete_data['layout'] = {
                            'furniture_positions': layout_data['layout'],
                            'placement_instructions': layout_data.get('placement_instructions', {}),
                            'room_dimensions': layout_data['room_dims'],
                            'furniture_count': layout_data['furniture_count']
                        }
                    
                    # Add furniture placement data if available
                    if st.session_state.furniture_placed and st.session_state.placement_data:
                        placement_data = st.session_state.placement_data
                        complete_data['furnished_room'] = {
                            'image_path': placement_data['path']
                        }
                    
                    # Add refined room data if available
                    if st.session_state.final_refined and st.session_state.refined_data:
                        refined_data = st.session_state.refined_data
                        complete_data['final_design'] = {
                            'image_path': refined_data['path']
                        }
                    
                    output_path = Path(__file__).parent / "complete_project.json"
                    with open(output_path, 'w') as f:
                        json.dump(complete_data, f, indent=2)
                    
                    st.success(f"Complete project saved to: {output_path}")
                    
                    # Download button
                    complete_json = json.dumps(complete_data, indent=2)
                    st.download_button(
                        label="Download Complete Project",
                        data=complete_json,
                        file_name="interior_design_complete.json",
                        mime="application/json",
                        use_container_width=True
                    )
                
                except Exception as e:
                    st.error(f"Error saving project: {str(e)}")

# --- Sidebar ---
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    1. **Select room type** (Bedroom or Living Room)
    2. **Choose design styles** (up to 3)
    3. **Select color palettes** (up to 3)
    4. **Set your budget range**
    5. **Pick preferred materials**
    6. **Share your lifestyle details**
    7. **Generate AI room description**
    8. **Find matching furniture** (top 3 per category)
    9. **Select 1 item** from each category
    10. **Upload room image** and process
    11. **Review dimensions**
    12. **Generate furniture layout**
    13. **Place furniture in room**
    14. **Refine with design theme**
    15. **Save complete project**
    """)
    
    st.divider()
    
    st.markdown("### Image Source")
    st.info("Images are loaded from Supabase cloud storage")
    
    if supabase:
        st.success("Connected to Supabase")
    else:
        st.error("⚠️ Supabase not configured")
    
    st.divider()
    
    st.markdown("### Progress")
    if st.session_state.user_input.get('ai_room_description'):
        st.success("Room description generated")
    else:
        st.info("Generate room description")
    
    if st.session_state.furniture_recommendations:
        st.success("Furniture recommendations loaded")
    else:
        st.info("Find matching furniture")
    
    if len(st.session_state.selected_furniture) == 4:
        st.success("All furniture selected (4/4)")
    elif len(st.session_state.selected_furniture) > 0:
        st.warning(f"{len(st.session_state.selected_furniture)}/4 items selected")
    else:
        st.info("Select furniture items")
    
    if st.session_state.room_processed:
        st.success("Room image processed")
    elif len(st.session_state.selected_furniture) == 4:
        st.info("Upload and process room image")
    else:
        st.caption("11.Process room image (after furniture)")
    
    if st.session_state.layout_generated:
        st.success("Layout generated")
    elif st.session_state.room_processed:
        st.info("Generate furniture layout")
    else:
        st.caption("Generate layout (after room processing)")
    
    if st.session_state.furniture_placed:
        st.success("Furniture placed")
    elif st.session_state.layout_generated:
        st.info("Place furniture in room")
    else:
        st.caption("Place furniture (after layout)")
    
    if st.session_state.final_refined:
        st.success("Final design complete")
    elif st.session_state.furniture_placed:
        st.info("Apply design theme")
    else:
        st.caption("Refine design (after placement)")
