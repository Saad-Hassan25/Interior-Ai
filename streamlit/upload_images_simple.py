"""
SIMPLE IMAGE UPLOADER FOR SUPABASE
This script uploads images using the Supabase Python client with SERVICE ROLE KEY.

The service role key has admin permissions and can:
- Create buckets
- Upload files
- Set policies

Get your service role key from:
https://app.supabase.com/project/asipcawpjvpwjyfcayvw/settings/api
"""

from pathlib import Path
from supabase import create_client, Client
import sys

# Try to load from secrets.toml first
try:
    import tomli
    secrets_path = Path(__file__).parent / '.streamlit' / 'secrets.toml'
    if secrets_path.exists():
        with open(secrets_path, 'rb') as f:
            secrets = tomli.load(f)
        SUPABASE_URL = secrets.get("SUPABASE_URL")
        SERVICE_KEY = secrets.get("SUPABASE_SERVICE_KEY")
        ANON_KEY = secrets.get("SUPABASE_ANON_KEY") or secrets.get("SUPABASE_KEY")
    else:
        raise FileNotFoundError("Secrets file not found")
except Exception as e:
    print(f"⚠️  Could not load from secrets.toml: {e}")
    # print("Using hardcoded values...\n")
    # SUPABASE_URL = ""
    # ANON_KEY = ""
    # SERVICE_KEY = None

# Use SERVICE_ROLE_KEY for uploads (has admin permissions)
UPLOAD_KEY = SERVICE_KEY if SERVICE_KEY and SERVICE_KEY != "YOUR_SERVICE_ROLE_KEY_HERE" else ANON_KEY

BUCKET_NAME = "interior-design-images"

def upload_all_images():
    """Upload all images to Supabase storage"""
    
    print("=" * 70)
    print("  SUPABASE IMAGE UPLOADER")
    print("=" * 70)
    print(f"\n📡 Connecting to: {SUPABASE_URL}")
    print(f"📦 Bucket: {BUCKET_NAME}")
    
    # Check which key we're using
    if UPLOAD_KEY == SERVICE_KEY and SERVICE_KEY:
        print("Using: SERVICE_ROLE_KEY (Admin permissions)\n")
    else:
        print("Using: ANON_KEY (Limited permissions)")
        print("If you get permission errors, add SERVICE_ROLE_KEY to secrets.toml\n")
    
    # Create client with appropriate key
    supabase: Client = create_client(SUPABASE_URL, UPLOAD_KEY)
    
    # Check if bucket exists, create if it doesn't (requires SERVICE_ROLE_KEY)
    try:
        buckets = supabase.storage.list_buckets()
        bucket_exists = any(b.name == BUCKET_NAME for b in buckets)
        
        if not bucket_exists:
            print(f"Bucket '{BUCKET_NAME}' does not exist!")
            
            # Try to create bucket if using service role key
            if UPLOAD_KEY == SERVICE_KEY and SERVICE_KEY:
                print(f"Attempting to create bucket with SERVICE_ROLE_KEY...")
                try:
                    supabase.storage.create_bucket(
                        BUCKET_NAME,
                        options={"public": True}
                    )
                    print(f"✅ Bucket '{BUCKET_NAME}' created successfully!\n")
                except Exception as create_error:
                    print(f"Could not create bucket: {create_error}")
                    print("\nPLEASE CREATE BUCKET MANUALLY:")
                    print("   1. Go to: https://app.supabase.com/project/asipcawpjvpwjyfcayvw/storage/buckets")
                    print("   2. Click 'New bucket'")
                    print(f"   3. Name: {BUCKET_NAME}")
                    print("   4. Make it PUBLIC ")
                    print("   5. Create bucket")
                    print("   6. Run this script again\n")
                    return False
            else:
                print("\nTO CREATE BUCKET:")
                print("   Option 1: Add SERVICE_ROLE_KEY to .streamlit/secrets.toml")
                print("             Get it from: https://app.supabase.com/project/asipcawpjvpwjyfcayvw/settings/api")
                print("   Option 2: Create manually:")
                print("             1. Go to: https://app.supabase.com/project/asipcawpjvpwjyfcayvw/storage/buckets")
                print("             2. Click 'New bucket'")
                print(f"             3. Name: {BUCKET_NAME}")
                print("             4. Make it PUBLIC ")
                print("             5. Create bucket and run script again\n")
                return False
        else:
            print(f"✅ Bucket '{BUCKET_NAME}' found!\n")
    except Exception as e:
        print(f"⚠️  Could not check buckets: {e}")
        print("Will attempt to upload anyway...\n")
    
    # Upload themes - both bedroom and living room
    print("-" * 70)
    print("UPLOADING THEME IMAGES")
    print("-" * 70)
    
    # Upload Living Room themes
    print("\nLiving Room Themes:")
    livingroom_dir = Path(__file__).parent / "LivingRoom Themes"
    
    if livingroom_dir.exists():
        livingroom_files = sorted(livingroom_dir.glob("*.jpeg"))
        print(f"Found {len(livingroom_files)} living room theme images\n")
        
        success_count = 0
        for img_file in livingroom_files:
            try:
                with open(img_file, 'rb') as f:
                    file_data = f.read()
                    
                # Upload with upsert=true to overwrite if exists
                result = supabase.storage.from_(BUCKET_NAME).upload(
                    f"livingroom-themes/{img_file.name}",
                    file_data,
                    file_options={"content-type": "image/jpeg", "upsert": "true"}
                )
                
                print(f"  ✅ {img_file.name}")
                success_count += 1
                
            except Exception as e:
                print(f"  {img_file.name}: {e}")
        
        print(f"\nLiving Room Themes: {success_count}/{len(livingroom_files)} uploaded")
    else:
        print("LivingRoom Themes folder not found")

    # Upload Bedroom themes
    print("\nBedroom Themes:")
    bedroom_dir = Path(__file__).parent / "BedRoom Themes"
    
    if bedroom_dir.exists():
        bedroom_files = sorted(bedroom_dir.glob("*.jpeg"))
        
        if len(bedroom_files) == 0:
            print("No bedroom theme images found.")
            print("Note: Add bedroom theme images to 'BedRoom Themes/' folder")
            print("    Image names must match theme names (e.g., Modern.jpeg)")
        else:
            print(f"Found {len(bedroom_files)} bedroom theme images\n")
            
            success_count = 0
            for img_file in bedroom_files:
                try:
                    with open(img_file, 'rb') as f:
                        file_data = f.read()
                        
                    result = supabase.storage.from_(BUCKET_NAME).upload(
                        f"bedroom-themes/{img_file.name}",
                        file_data,
                        file_options={"content-type": "image/jpeg", "upsert": "true"}
                    )
                    
                    print(f"  ✅ {img_file.name}")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ❌ {img_file.name}: {e}")
            
            print(f"\nBedroom Themes: {success_count}/{len(bedroom_files)} uploaded")
    else:
        print("⚠️  BedRoom Themes folder not found")
    
    # Upload colors
    print("\n" + "-" * 70)
    print("📤 UPLOADING COLOR PALETTE IMAGES")
    print("-" * 70)
    
    colors_dir = Path(__file__).parent / "Colors"
    color_files = sorted(colors_dir.glob("*.jpeg"))
    
    print(f"Found {len(color_files)} color palette images\n")
    
    success_count = 0
    for img_file in color_files:
        try:
            with open(img_file, 'rb') as f:
                file_data = f.read()
                
            result = supabase.storage.from_(BUCKET_NAME).upload(
                f"colors/{img_file.name}",
                file_data,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            
            print(f"  ✅ {img_file.name}")
            success_count += 1
            
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower():
                try:
                    supabase.storage.from_(BUCKET_NAME).update(
                        f"colors/{img_file.name}",
                        file_data,
                        file_options={"content-type": "image/jpeg"}
                    )
                    print(f"  ✅ {img_file.name} (updated)")
                    success_count += 1
                except Exception as e2:
                    print(f"  ❌ {img_file.name}: {e2}")
            else:
                print(f"  ❌ {img_file.name}: {e}")
    
    print(f"\nColors: {success_count}/{len(color_files)} uploaded")
    
    # Summary
    print("\n" + "=" * 70)
    print("  UPLOAD SUMMARY")
    print("=" * 70)
    print(f"\nUpload process complete!")
    print(f"\nTest image URLs:")
    print(f"   Living Room Theme: {SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/livingroom-themes/Modern.jpeg")
    print(f"   Bedroom Theme: {SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/bedroom-themes/Modern.jpeg")
    print(f"   Color: {SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/colors/Warm%20Neutral.jpeg")
    print(f"\n🚀 Run the app: streamlit run app.py\n")
    
    return True

if __name__ == "__main__":
    try:
        upload_all_images()
    except KeyboardInterrupt:
        print("\n\n⚠️  Upload cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
