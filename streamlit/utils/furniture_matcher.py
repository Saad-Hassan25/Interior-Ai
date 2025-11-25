from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from supabase import Client
import streamlit as st
from huggingface_hub import login

# Embedding model (same as used in inventory setup)
EMBEDDING_MODEL_NAME = "google/embeddinggemma-300m"

class FurnitureMatcher:
    """Find furniture items matching user preferences using semantic search"""
    
    def __init__(self, supabase_client: Client):
        """
        Initialize the furniture matcher
        
        Args:
            supabase_client: Initialized Supabase client
        """
        self.supabase = supabase_client
        self.embedding_model = None
        self._login_hf()  # Log in to Hugging Face on initialization

    def _login_hf(self):
        """Login to Hugging Face using token stored in Streamlit secrets"""
        try:
            hf_token = st.secrets["huggingface_token"]
            login(token=hf_token)
            print("✅ Logged in to Hugging Face Hub")
        except KeyError:
            print("⚠️ Hugging Face token not found in secrets.toml. Gated models may fail to load.")

    def load_embedding_model(self):
        """Load the sentence transformer model for embeddings"""
        if self.embedding_model is None:
            print(f"📥 Loading embedding model: {EMBEDDING_MODEL_NAME}")
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
            print("✅ Embedding model loaded")
        return self.embedding_model
    
    def generate_query_embedding(self, room_description: str) -> List[float]:
        """Generate embedding vector for the room description"""
        if self.embedding_model is None:
            self.load_embedding_model()
        
        embedding = self.embedding_model.encode(room_description, convert_to_tensor=False)
        return embedding.tolist()
    
    # rest of the methods remain unchanged

    
    def find_similar_furniture(
        self, 
        query_embedding: List[float], 
        category: str, 
        top_k: int = 3
    ) -> List[Dict]:
        """
        Find top K similar furniture items in a category using vector similarity
        
        Args:
            query_embedding: Embedding vector of the room description
            category: Furniture category (beds, chairs, sofas, tables)
            top_k: Number of top results to return (default: 3)
            
        Returns:
            List of furniture items with similarity scores
        """
        try:
            # Use Supabase RPC function for vector similarity search
            # The function uses cosine similarity: 1 - cosine_distance
            result = self.supabase.rpc(
                'match_furniture',
                {
                    'query_embedding': query_embedding,
                    'match_category': category,
                    'match_count': top_k
                }
            ).execute()
            
            if result.data:
                return result.data
            else:
                print(f"⚠️ No results found for category: {category}")
                return []
                
        except Exception as e:
            print(f"❌ Error finding similar furniture for {category}: {str(e)}")
            # Fallback: Get random items from category
            return self._get_fallback_items(category, top_k)
    
    def _get_fallback_items(self, category: str, limit: int) -> List[Dict]:
        """Fallback method to get items when vector search fails"""
        try:
            result = self.supabase.table('furniture_inventory')\
                .select('*')\
                .eq('category', category)\
                .limit(limit)\
                .execute()
            
            if result.data:
                # Add a default similarity score
                for item in result.data:
                    item['similarity'] = 0.5
                return result.data
            return []
        except Exception as e:
            print(f"❌ Fallback also failed for {category}: {str(e)}")
            return []
    
    def get_recommendations_for_all_categories(
        self, 
        room_description: str, 
        categories: List[str] = None,
        top_k: int = 3
    ) -> Dict[str, List[Dict]]:
        """
        Get furniture recommendations for all categories
        
        Args:
            room_description: AI-generated room description
            categories: List of categories to search (default: all)
            top_k: Number of recommendations per category
            
        Returns:
            Dictionary mapping category to list of recommended items
        """
        if categories is None:
            categories = ['beds', 'chairs', 'sofas', 'tables']
        
        # Generate embedding for room description
        print("🧠 Generating embedding for room description...")
        query_embedding = self.generate_query_embedding(room_description)
        print(f"✅ Embedding generated ({len(query_embedding)} dimensions)")
        
        recommendations = {}
        
        for category in categories:
            print(f"\n🔍 Finding top {top_k} {category}...")
            items = self.find_similar_furniture(query_embedding, category, top_k)
            recommendations[category] = items
            
            if items:
                print(f"✅ Found {len(items)} {category}")
            else:
                print(f"⚠️ No {category} found")
        
        return recommendations
    
    def format_recommendations_for_display(
        self, 
        recommendations: Dict[str, List[Dict]]
    ) -> Dict[str, List[Dict]]:
        """
        Format recommendations for Streamlit display
        
        Args:
            recommendations: Raw recommendations from database
            
        Returns:
            Formatted recommendations with cleaned data
        """
        formatted = {}
        
        for category, items in recommendations.items():
            formatted[category] = []
            
            for item in items:
                formatted_item = {
                    'id': item.get('id'),
                    'name': item.get('name', '').replace('buy-', '').replace('_', ' ').title(),
                    'original_name': item.get('name', ''),
                    'category': item.get('category', ''),
                    'description': item.get('description', ''),
                    'image_url': item.get('image_url', ''),
                    'length': item.get('length', 0),
                    'width': item.get('width', 0),
                    'similarity': round(item.get('similarity', 0) * 100, 1)  # Convert to percentage
                }
                formatted[category].append(formatted_item)
        
        return formatted


def save_user_selections(
    user_preferences: Dict,
    selected_furniture: Dict[str, Dict],
    output_filename: str = "user_final_selections.json"
) -> str:
    """
    Save user's furniture selections along with their preferences
    
    Args:
        user_preferences: Original user preferences with room description
        selected_furniture: User's selected furniture items by category
        output_filename: Name of output JSON file
        
    Returns:
        Path to saved file
    """
    import json
    from pathlib import Path
    
    # Combine preferences and selections
    final_data = {
        'user_preferences': user_preferences,
        'selected_furniture': selected_furniture,
        'total_items_selected': len(selected_furniture)
    }
    
    # Save to file
    output_path = Path(__file__).parent.parent / output_filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)
    
    return str(output_path)
