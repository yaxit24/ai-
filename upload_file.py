import os
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get Supabase credentials
supabase_url = os.environ.get("SUPABASE_URL") or input("Enter your Supabase URL: ")
supabase_key = os.environ.get("SUPABASE_KEY") or input("Enter your Supabase anon key: ")

print(f"Connecting to Supabase at {supabase_url}")
supabase = create_client(supabase_url, supabase_key)

# Function to upload file
def upload_file(file_path, dest_path=None):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found!")
        return False
    
    # Use filename if no destination path provided
    if not dest_path:
        dest_path = os.path.basename(file_path)
    
    try:
        print(f"Reading file {file_path}...")
        with open(file_path, "rb") as f:
            file_contents = f.read()
            
        print(f"Uploading {len(file_contents)} bytes to {dest_path}...")
        result = supabase.storage.from_("transcripts").upload(
            dest_path,
            file_contents,
            {"content-type": "application/pdf", "upsert": True}
        )
        
        print(f"Upload result: {result}")
        return True
            
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        return False

# Insert record into transcripts table
def insert_transcript_record(course_name, week_number, transcript_name, file_path):
    try:
        # Check if table exists
        try:
            supabase.table("transcripts").select("count", "exact").execute()
        except:
            print("Creating transcripts table...")
            sql = """
CREATE TABLE IF NOT EXISTS transcripts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_name TEXT NOT NULL,
  week_number INTEGER,
  transcript_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
            """
            supabase.query(sql).execute()
            print("Table created successfully!")
        
        # Insert record
        result = supabase.table("transcripts").insert({
            "course_name": course_name,
            "week_number": week_number,
            "transcript_name": transcript_name,
            "file_path": file_path
        }).execute()
        
        print(f"Database insert result: {result}")
        return True
    except Exception as e:
        print(f"Error inserting record: {str(e)}")
        return False

# Main execution
if __name__ == "__main__":
    print("=== Supabase File Uploader ===")
    
    # Get file info
    file_path = input("Enter the full path to your PDF file: ")
    course_name = input("Enter course name: ")
    week_number = int(input("Enter week number: "))
    transcript_name = input("Enter transcript name: ")
    
    # Generate destination path - use simple filename to avoid path issues
    dest_path = os.path.basename(file_path)
    
    # Upload file
    if upload_file(file_path, dest_path):
        print("File uploaded successfully!")
        
        # Insert record
        if insert_transcript_record(course_name, week_number, transcript_name, dest_path):
            print("Record inserted successfully!")
            print(f"✅ All done! You can now use this file in the app with file path: {dest_path}")
        else:
            print("❌ Failed to insert record, but file was uploaded.")
    else:
        print("❌ Failed to upload file.") 