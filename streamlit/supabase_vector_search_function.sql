-- ============================================================================
-- Supabase Function for Furniture Vector Similarity Search
-- This function finds furniture items similar to a query embedding
-- ============================================================================

-- Create the match_furniture function for semantic search
CREATE OR REPLACE FUNCTION match_furniture(
    query_embedding vector(384),
    match_category text,
    match_count int DEFAULT 3
)
RETURNS TABLE (
    id bigint,
    name text,
    category text,
    description text,
    image_url text,
    length decimal,
    width decimal,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        furniture_inventory.id,
        furniture_inventory.name,
        furniture_inventory.category,
        furniture_inventory.description,
        furniture_inventory.image_url,
        furniture_inventory.length,
        furniture_inventory.width,
        1 - (furniture_inventory.embedding <=> query_embedding) AS similarity
    FROM furniture_inventory
    WHERE furniture_inventory.category = match_category
    ORDER BY furniture_inventory.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ============================================================================
-- Test the function (example)
-- ============================================================================

-- First, get a sample embedding from an existing item to test
/*
SELECT embedding FROM furniture_inventory LIMIT 1;

-- Then test the function with that embedding
-- Replace the vector values with actual embedding from above query
SELECT * FROM match_furniture(
    '[0.1, 0.2, ...]'::vector(384),  -- Your query embedding here
    'sofas',  -- Category
    3  -- Number of results
);
*/

-- ============================================================================
-- Grant execute permissions
-- ============================================================================

-- Allow public to execute the function (for read-only access)
GRANT EXECUTE ON FUNCTION match_furniture TO anon;
GRANT EXECUTE ON FUNCTION match_furniture TO authenticated;

-- ============================================================================
-- Verification
-- ============================================================================

-- Check if function exists
SELECT 
    routine_name,
    routine_type,
    data_type
FROM information_schema.routines
WHERE routine_name = 'match_furniture';

-- ============================================================================
