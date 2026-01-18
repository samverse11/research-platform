# backend/crawler/test_env_load.py
from pathlib import Path
import os

# Method 1: Check file exists
env_path = Path(__file__).parent / ".env"
print(f"1. Looking for .env at: {env_path}")
print(f"2. File exists: {env_path.exists()}")
print(f"3. File size: {env_path.stat().st_size if env_path.exists() else 'N/A'} bytes\n")

# Method 2: Try loading with dotenv
try:
    from dotenv import load_dotenv
    load_dotenv(env_path)
    print("4.  Loaded with dotenv ✅\n")
    
    springer = os.getenv("SPRINGER_API_KEY")
    ieee = os.getenv("IEEE_API_KEY")
    
    print(f"5. SPRINGER_API_KEY: {'SET ✅' if springer else 'NOT SET ❌'}")
    if springer:
        print(f"   Length: {len(springer)}")
        print(f"   Preview: {springer[:15]}.. .\n")
    
    print(f"6. IEEE_API_KEY: {'SET ✅' if ieee else 'NOT SET ❌'}")
    if ieee:
        print(f"   Length: {len(ieee)}")
        print(f"   Preview: {ieee[:15]}...\n")
    
except ImportError:
    print("4. python-dotenv NOT installed ❌")
    print("   Install it:  pip install python-dotenv\n")

# Method 3: Try with pydantic-settings
try:
    from app.config import get_settings
    settings = get_settings()
    
    print("7. Loaded with pydantic-settings ✅\n")
    print(f"8. settings.SPRINGER_API_KEY:  {'SET ✅' if settings.SPRINGER_API_KEY else 'NOT SET ❌'}")
    if settings.SPRINGER_API_KEY:
        print(f"   Length: {len(settings.SPRINGER_API_KEY)}")
        print(f"   Preview: {settings. SPRINGER_API_KEY[:15]}...\n")
    
    print(f"9. settings. IEEE_API_KEY: {'SET ✅' if settings.IEEE_API_KEY else 'NOT SET ❌'}")
    if settings.IEEE_API_KEY:
        print(f"   Length: {len(settings.IEEE_API_KEY)}")
        print(f"   Preview: {settings.IEEE_API_KEY[: 15]}...\n")
        
except Exception as e:
    print(f"7. pydantic-settings failed ❌")
    print(f"   Error: {e}\n")

# Method 4: Read file manually
if env_path.exists():
    print("10. File contents:")
    print("-" * 50)
    with open(env_path, 'r') as f:
        content = f.read()
        print(content)
    print("-" * 50)