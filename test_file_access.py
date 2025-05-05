import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Supabase credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://lhrtpvkplpgkpqnsigzm.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxocnRwdmtwbHBna3BxbnNpZ3ptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTQ3MjQ3OTMsImV4cCI6MjAzMDMwMDc5M30.jfFhEDC1H_lfdsPkXyfuR9a5tJ4Xb2HJiNfq0Swji0"
FILE_PATH = "c1-w1.pdf"

def test_file_exists():
    """Check if file exists in Supabase storage"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    
    # Get public URL
    url = f"{SUPABASE_URL}/storage/v1/object/public/transcripts/{FILE_PATH}"
    print(f"Testing URL: {url}")
    
    response = requests.head(url, headers=headers)
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ File exists and is accessible!")
        return True
    else:
        print("❌ File does not exist or is not accessible.")
        return False

def test_record_exists():
    """Check if record exists in transcripts table"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/transcripts?file_path=eq.{FILE_PATH}"
    print(f"Testing URL: {url}")
    
    response = requests.get(url, headers=headers)
    print(f"Response status: {response.status_code}")
    print(f"Response content: {response.text}")
    
    if response.status_code == 200 and response.text != "[]":
        print("✅ Record exists in the database!")
        return True
    else:
        print("❌ Record does not exist in the database.")
        return False

if __name__ == "__main__":
    print("=== Testing Supabase File Access ===")
    
    # Test file access
    file_exists = test_file_exists()
    
    # Test record existence
    record_exists = test_record_exists()
    
    if file_exists and record_exists:
        print("\n✅ All good! File and record both exist.")
        print("You should be able to use the app now.")
    elif file_exists:
        print("\n⚠️ File exists but record is missing.")
        print("You need to create a record in the transcripts table.")
    elif record_exists:
        print("\n⚠️ Record exists but file is missing or not accessible.")
        print("You need to upload the file to the transcripts bucket.")
    else:
        print("\n❌ Both file and record are missing.")
        print("Follow these steps manually:")
        print("1. Log in to Supabase Dashboard")
        print("2. Create a 'transcripts' bucket (public)")
        print("3. Upload c1-w1.pdf to the bucket")
        print("4. Create a record in the transcripts table")
        print("   - course_name: AI for Everyone")
        print("   - week_number: 1")
        print("   - transcript_name: Week 1 Introduction")
        print("   - file_path: c1-w1.pdf") 