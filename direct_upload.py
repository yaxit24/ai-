import os
import requests
import json
import base64

# Hardcoded Supabase credentials - replace with your actual values
SUPABASE_URL = "https://lhrtpvkplpgkpqnsigzm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxocnRwdmtwbHBna3BxbnNpZ3ptIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTQ3MjQ3OTMsImV4cCI6MjAzMDMwMDc5M30.jfFhEDC1H_lfdsPkXyfuR9a5tJ4Xb2HJiNfq0Swji0"

# Hardcoded file values - update these to match your needs
PDF_PATH = "c1-w1.pdf"  # Place your PDF in the current directory with this name
COURSE_NAME = "AI for Everyone"
WEEK_NUMBER = 1
TRANSCRIPT_NAME = "Week 1 Introduction"

def upload_file_using_requests():
    """Upload file using direct HTTP requests to Supabase"""
    if not os.path.exists(PDF_PATH):
        print(f"Error: File {PDF_PATH} not found!")
        return False
    
    # Read file
    print(f"Reading file {PDF_PATH}...")
    with open(PDF_PATH, "rb") as f:
        file_data = f.read()
    
    # Upload to storage using REST API
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/pdf"
    }
    
    storage_url = f"{SUPABASE_URL}/storage/v1/object/transcripts/{PDF_PATH}"
    
    try:
        print(f"Uploading {len(file_data)} bytes to {storage_url}...")
        response = requests.post(
            storage_url,
            headers=headers,
            data=file_data
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("✅ File uploaded successfully!")
            return True
        else:
            print(f"⚠️ Upload failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error uploading: {e}")
        return False

def insert_record_using_requests():
    """Insert transcript record using direct HTTP requests"""
    # Prepare data
    data = {
        "course_name": COURSE_NAME,
        "week_number": WEEK_NUMBER,
        "transcript_name": TRANSCRIPT_NAME,
        "file_path": PDF_PATH
    }
    
    # Set headers
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Insert using REST API
    table_url = f"{SUPABASE_URL}/rest/v1/transcripts"
    
    try:
        print(f"Inserting record to {table_url}...")
        response = requests.post(
            table_url,
            headers=headers,
            data=json.dumps(data)
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("✅ Record inserted successfully!")
            return True
        else:
            print(f"⚠️ Insert failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"Error inserting record: {e}")
        return False

if __name__ == "__main__":
    print("=== Direct Supabase Upload Using Requests ===")
    print(f"File: {PDF_PATH}")
    print(f"Course: {COURSE_NAME}")
    print(f"Week: {WEEK_NUMBER}")
    
    # Upload file
    upload_success = upload_file_using_requests()
    
    if upload_success:
        # Insert record
        record_success = insert_record_using_requests()
        
        if record_success:
            print("\n✅ Success! Both file and record were added.")
            print(f"The file path in the database is: {PDF_PATH}")
            print(f"You can now use the app to summarize {COURSE_NAME}, Week {WEEK_NUMBER}")
        else:
            print("\n⚠️ File was uploaded but metadata record failed.")
            print("You can add the record manually via Supabase dashboard.")
    else:
        print("\n❌ Failed to upload file.")
        print("Please check Supabase credentials and permissions.") 