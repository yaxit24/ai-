import streamlit as st
import os
from dotenv import load_dotenv
import openai
from supabase import create_client
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex, Settings
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
import fitz  # PyMuPDF
import tempfile
import uuid
import base64

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="Coursera Study Buddy",
    page_icon="📚",
    layout="wide",
)

# Initialize API clients
try:
    # OpenAI
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        openai.api_key = st.secrets.get("OPENAI_API_KEY")
    
    # Supabase
    supabase_url = os.environ.get("SUPABASE_URL") 
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_KEY")
    
    # Debug information for Supabase credentials
    if not supabase_url or not supabase_key:
        st.error("❌ Supabase credentials are missing. Please check your .env file or Streamlit secrets.")
        st.info("Make sure you have set up SUPABASE_URL and SUPABASE_KEY in your environment variables or secrets.")
        apis_configured = False
    else:
        # Mask the key for security but show enough to verify it's loading correctly
        masked_key = supabase_key[:5] + "*" * (len(supabase_key) - 10) + supabase_key[-5:] if len(supabase_key) > 10 else "***"
        st.sidebar.expander("Debug Info", expanded=False).write(f"""
        **Supabase Configuration:**
        - URL: {supabase_url}
        - Key: {masked_key}
        """)
        
        # Initialize Supabase client with debug information
        try:
            supabase = create_client(supabase_url, supabase_key)
            st.sidebar.expander("Debug Info", expanded=False).success("✅ Supabase connection initialized successfully")
        except Exception as supabase_error:
            st.error(f"❌ Failed to initialize Supabase client: {str(supabase_error)}")
            st.info("Check that your Supabase URL and key are correct and that your project is active.")
            apis_configured = False
            raise
    
    # Pinecone
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")
    pinecone_env = os.environ.get("PINECONE_ENVIRONMENT", "us-east-1")
    if not pinecone_api_key:
        pinecone_api_key = st.secrets.get("PINECONE_API_KEY")
    pc = Pinecone(api_key=pinecone_api_key)
    pinecone_index_name = "coursera-transcripts"
    
    apis_configured = True
except Exception as e:
    st.error(f"Error initializing APIs: {str(e)}")
    apis_configured = False

# Create sidebar
st.sidebar.title("Coursera Study Buddy")
st.sidebar.info("Upload Coursera transcripts and interact with them using AI.")

# Add configuration check button to sidebar
if st.sidebar.button("🔍 Check Configuration"):
    st.sidebar.write("Checking system configuration...")
    
    # Check OpenAI API
    try:
        # Simple test request to OpenAI API
        import openai
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        st.sidebar.success("✅ OpenAI API connection successful")
    except Exception as e:
        st.sidebar.error(f"❌ OpenAI API error: {str(e)}")
    
    # Check Supabase connection
    try:
        # Try listing buckets
        buckets = supabase.storage.list_buckets()
        st.sidebar.success(f"✅ Supabase connection successful. Found {len(buckets)} buckets")
        # Check for transcripts bucket
        if any(bucket['name'] == 'transcripts' for bucket in buckets):
            st.sidebar.success("✅ 'transcripts' bucket exists")
        else:
            st.sidebar.warning("⚠️ 'transcripts' bucket not found")
            
        # Check database table
        try:
            result = supabase.table("transcripts").select("count", "exact").execute()
            st.sidebar.success("✅ 'transcripts' database table exists")
        except:
            st.sidebar.warning("⚠️ 'transcripts' database table not found")
    except Exception as e:
        st.sidebar.error(f"❌ Supabase error: {str(e)}")
    
    # Check Pinecone
    try:
        # List indexes
        indexes = pc.list_indexes()
        st.sidebar.success(f"✅ Pinecone connection successful. Found {len(indexes)} indexes")
        
        # Check for coursera-transcripts index
        if any(index.name == pinecone_index_name for index in indexes):
            st.sidebar.success(f"✅ '{pinecone_index_name}' index exists")
        else:
            st.sidebar.warning(f"⚠️ '{pinecone_index_name}' index not found")
    except Exception as e:
        st.sidebar.error(f"❌ Pinecone error: {str(e)}")

# Main app tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Upload", "Summarize", "Ask Questions", "Generate Quiz", "Exam Prep"])

# Helper functions
def extract_text_from_pdf(pdf_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        temp_file.write(pdf_file.getvalue())
        temp_path = temp_file.name
    
    text = ""
    try:
        doc = fitz.open(temp_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        st.error(f"Error extracting text: {str(e)}")
    finally:
        os.unlink(temp_path)
    
    return text

def setup_bucket_permissions():
    """Set appropriate permissions for the transcripts bucket"""
    try:
        # List buckets to check if transcripts exists
        buckets = supabase.storage.list_buckets()
        if not any(bucket['name'] == 'transcripts' for bucket in buckets):
            # Create the bucket if it doesn't exist
            supabase.storage.create_bucket("transcripts", {"public": True})
            st.success("Created 'transcripts' bucket with public access")
        
        # Try to create a policy that allows all operations (for testing purposes)
        # Note: This function is not in the Supabase Python client, so we use SQL
        try:
            sql = """
            BEGIN;
            -- Drop existing policies to avoid conflicts
            DROP POLICY IF EXISTS "Allow all operations for all users" ON storage.objects;
            
            -- Create a policy that allows all operations for authenticated and anon users
            CREATE POLICY "Allow all operations for all users" 
            ON storage.objects
            FOR ALL 
            TO authenticated, anon
            USING (true)
            WITH CHECK (true);
            
            COMMIT;
            """
            supabase.query(sql).execute()
            st.success("Set permissive storage policies for testing")
        except Exception as policy_error:
            st.warning(f"Could not set bucket policies via SQL: {str(policy_error)}")
            st.info("You may need to set bucket policies manually in the Supabase dashboard")
            st.info("Go to Storage → Policies and enable public access for testing")
        
        return True
    except Exception as e:
        st.error(f"Error setting up bucket permissions: {str(e)}")
        return False

def upload_file_to_database(file_content, file_name, course_name, week_number, transcript_name):
    """Upload file directly to database as base64 rather than storage"""
    try:
        # Encode file content as base64
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        # Check if table exists and create if needed
        try:
            # Check if file_content table exists
            supabase.table("file_contents").select("count", "exact").execute()
        except:
            # Create the table
            sql = """
CREATE TABLE IF NOT EXISTS file_contents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_name TEXT NOT NULL,
  week_number INTEGER,
  transcript_name TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_data TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
            """
            supabase.query(sql).execute()
            st.success("Created file_contents table for direct file storage")
        
        # Insert the file content into the database
        result = supabase.table("file_contents").insert({
            "course_name": course_name,
            "week_number": week_number,
            "transcript_name": transcript_name,
            "file_name": file_name,
            "file_data": file_base64
        }).execute()
        
        return True, result
    except Exception as e:
        return False, str(e)

def get_file_data_from_database(course_name, week_number=None, file_name=None):
    """Retrieve file content from database"""
    try:
        query = supabase.table("file_contents").select("*").eq("course_name", course_name)
        
        if week_number:
            query = query.eq("week_number", week_number)
        
        if file_name:
            query = query.eq("file_name", file_name)
            
        result = query.execute()
        return result.data
    except Exception as e:
        st.error(f"Error retrieving file data: {str(e)}")
        return []

def get_file_from_supabase(file_path):
    """Download a file from Supabase storage and return its contents"""
    try:
        response = supabase.storage.from_("transcripts").download(file_path)
        return response
    except Exception as e:
        st.error(f"Error downloading file from Supabase: {str(e)}")
        # Try to find the file locally
        local_paths = [
            file_path,  # Try direct path
            os.path.join(os.getcwd(), file_path),  # Try in current directory
            os.path.join(os.path.expanduser("~"), "Downloads", file_path)  # Try in Downloads folder
        ]
        
        for path in local_paths:
            if os.path.exists(path):
                st.info(f"Found file locally at {path}, using this instead")
                with open(path, "rb") as f:
                    return f.read()
        
        return None

def extract_text_from_supabase_pdf(file_path):
    """Download a PDF from Supabase and extract its text"""
    # Check if this is a DB-stored file
    if file_path.startswith("DB_"):
        # Extract the original filename
        filename = file_path[3:]  # Remove the "DB_" prefix
        st.info(f"Retrieving file {filename} from database storage...")
        # Need to find the record in the database
        try:
            # Find all records that might match this filename
            results = supabase.table("file_contents").select("*").ilike("file_name", filename).execute()
            if results.data:
                # Use the first match
                file_record = results.data[0]
                # Decode the base64 data
                file_data = base64.b64decode(file_record["file_data"])
                
                # Write to temp file and extract text
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(file_data)
                    temp_path = temp_file.name
                
                text = ""
                try:
                    doc = fitz.open(temp_path)
                    for page in doc:
                        text += page.get_text()
                    doc.close()
                    return text
                except Exception as e:
                    st.error(f"Error extracting text from database-stored PDF: {str(e)}")
                finally:
                    os.unlink(temp_path)
                    
                return ""
            else:
                st.error(f"Could not find file {filename} in database")
                return ""
        except Exception as e:
            st.error(f"Error retrieving file from database: {str(e)}")
            return ""
            
    # Regular storage file
    pdf_data = get_file_from_supabase(file_path)
    if not pdf_data:
        return ""
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        temp_file.write(pdf_data)
        temp_path = temp_file.name
    
    text = ""
    try:
        doc = fitz.open(temp_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        st.error(f"Error extracting text from downloaded PDF: {str(e)}")
    finally:
        os.unlink(temp_path)
    
    return text

def get_settings():
    """Get LlamaIndex settings with the configured models"""
    # Create the embedding and LLM models
    embed_model = OpenAIEmbedding()
    llm = OpenAI(model="gpt-3.5-turbo", temperature=0.1)
    
    # Set the global settings directly
    Settings.llm = llm
    Settings.embed_model = embed_model
    
    # Return the configured Settings object
    return Settings

def get_vector_index():
    pinecone_index = pc.Index(pinecone_index_name)
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    settings = get_settings()
    return VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=settings.embed_model
    )

# Main application logic for each tab
with tab1:
    st.header("Upload Coursera Transcripts")
    
    # Add button to check and fix bucket permissions
    if st.button("⚙️ Setup Storage & Tables"):
        with st.spinner("Setting up Supabase storage..."):
            # Setup bucket permissions
            if setup_bucket_permissions():
                st.success("Supabase storage is now configured!")
            
            # Check if transcripts table exists
            try:
                # Try a simple query to see if the table exists
                result = supabase.table("transcripts").select("count", "exact").execute()
                st.success("✅ Transcripts table exists!")
            except Exception:
                # Create the table if it doesn't exist
                try:
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
                    st.success("✅ Created transcripts table!")
                except Exception as table_error:
                    st.error(f"❌ Error creating table: {str(table_error)}")
    
    course_name = st.text_input("Course Name", placeholder="e.g., Machine Learning")
    week_number = st.number_input("Week Number", min_value=1, max_value=20, value=1)
    transcript_name = st.text_input("Transcript Name", placeholder="e.g., Lecture 1 - Introduction")
    
    uploaded_file = st.file_uploader("Upload Transcript (PDF)", type="pdf")
    
    if st.button("Upload and Index") and uploaded_file and course_name and transcript_name:
        with st.spinner("Processing transcript..."):
            # Extract text
            text = extract_text_from_pdf(uploaded_file)
            if not text:
                st.error("Could not extract text from the PDF.")
            else:
                try:
                    st.write("Extracted text successfully. Now uploading...")
                    
                    # Try using normal Supabase storage upload first
                    storage_upload_success = False
                    
                    # Save file to Supabase
                    file_path = f"{course_name}_{week_number}_{uploaded_file.name}"
                    
                    # Try to upload the file directly without complex path
                    try:
                        # Debug info about the file being uploaded
                        st.write(f"Uploading file: {uploaded_file.name}")
                        st.write(f"File size: {len(uploaded_file.getvalue())} bytes")
                        st.write(f"Simple path: {file_path}")
                        
                        # More debugging info about Supabase connection
                        st.write("Checking Supabase credentials and bucket...")
                        buckets = supabase.storage.list_buckets()
                        st.write(f"Available buckets: {[bucket['name'] for bucket in buckets]}")
                        
                        # Check if transcripts bucket exists and create if needed
                        transcript_bucket_exists = any(bucket['name'] == 'transcripts' for bucket in buckets)
                        if not transcript_bucket_exists:
                            st.warning("'transcripts' bucket not found. Creating it now...")
                            try:
                                supabase.storage.create_bucket("transcripts", {"public": False})
                                st.success("Created 'transcripts' bucket!")
                            except Exception as bucket_error:
                                st.error(f"Error creating bucket: {str(bucket_error)}")
                        
                        # Direct upload with explicit content type
                        file_bytes = uploaded_file.getvalue()
                        st.write(f"Attempting to upload {len(file_bytes)} bytes...")
                        
                        # Try uploading using raw file bytes
                        upload_result = supabase.storage.from_("transcripts").upload(
                            file_path,
                            file_bytes,
                            {"content-type": "application/pdf", "upsert": True}
                        )
                        
                        st.write(f"Upload result: {upload_result}")
                        st.success("File uploaded to Supabase storage successfully!")
                        storage_upload_success = True
                        
                        # Verify the file exists in storage
                        try:
                            # List files in bucket to verify upload
                            files = supabase.storage.from_("transcripts").list()
                            st.write(f"Files in transcripts bucket: {files}")
                            
                            # Check if our file is in the list
                            if any(f["name"] == file_path for f in files):
                                st.success(f"✅ Verified file {file_path} exists in storage!")
                            else:
                                st.warning(f"⚠️ Could not verify file {file_path} in storage listing.")
                                storage_upload_success = False
                        except Exception as list_error:
                            st.warning(f"Could not verify file in storage: {str(list_error)}")
                        
                    except Exception as upload_error:
                        st.error(f"Error uploading file to Supabase: {str(upload_error)}")
                        
                        # Try with alternative file path
                        try:
                            st.info("Trying alternative upload method...")
                            # Try with simpler file name only
                            simple_path = uploaded_file.name
                            
                            # Upload with file name only
                            upload_result = supabase.storage.from_("transcripts").upload(
                                simple_path,
                                uploaded_file.getvalue(),
                                {"content-type": "application/pdf", "upsert": True}
                            )
                            
                            st.success(f"File uploaded with simplified path: {simple_path}")
                            file_path = simple_path  # Update the file path for database record
                            storage_upload_success = True
                            
                            # Verify upload
                            files = supabase.storage.from_("transcripts").list()
                            st.write(f"Files in bucket after simplified upload: {files}")
                        except Exception as alt_error:
                            st.error(f"Alternative upload also failed: {str(alt_error)}")
                            st.error("Will try direct database storage instead.")
                            storage_upload_success = False
                    
                    # If storage upload failed, try direct database upload as fallback
                    if not storage_upload_success:
                        st.info("Using direct database storage as fallback...")
                        db_upload_success, result = upload_file_to_database(
                            uploaded_file.getvalue(),
                            uploaded_file.name,
                            course_name,
                            week_number,
                            transcript_name
                        )
                        
                        if db_upload_success:
                            st.success("File uploaded directly to database successfully!")
                            file_path = f"DB_{uploaded_file.name}"  # Mark file path as database stored
                        else:
                            st.error(f"Database upload failed: {result}")
                            st.error("All upload methods failed. Please check your Supabase configuration.")
                            st.stop()
                    
                    # Save metadata to Supabase
                    try:
                        # First check if the table exists
                        try:
                            # Try a simple query to see if the table exists
                            supabase.table("transcripts").select("count", "exact").execute()
                        except Exception as table_error:
                            st.error(f"Error accessing 'transcripts' table: {str(table_error)}")
                            st.info("Please make sure you created the 'transcripts' table in your Supabase project with the correct structure.")
                            st.code("""
CREATE TABLE transcripts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_name TEXT NOT NULL,
  week_number INTEGER,
  transcript_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
                            """, language="sql")
                            
                            # Create table automatically without asking
                            try:
                                # Attempt to create the table using raw SQL
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
                                # Execute the SQL
                                supabase.query(sql).execute()
                                st.success("Successfully created 'transcripts' table!")
                                # Verify table exists
                                result = supabase.table("transcripts").select("count", "exact").execute()
                                st.write(f"Table check result: {result}")
                            except Exception as create_table_error:
                                st.error(f"Failed to create table: {str(create_table_error)}")
                                st.info("You need to create the table manually in the Supabase dashboard.")
                                st.stop()
                        
                        # Insert the record
                        supabase.table("transcripts").insert({
                            "course_name": course_name,
                            "week_number": week_number,
                            "transcript_name": transcript_name,
                            "file_path": file_path
                        }).execute()
                        st.success("Metadata saved to Supabase database successfully!")
                    except Exception as db_error:
                        st.error(f"Error saving metadata: {str(db_error)}")
                        st.stop()
                    
                    # Index transcript in Pinecone (optional - may skip if having issues)
                    try:
                        from llama_index.core import Document
                        from llama_index.core.node_parser import SimpleNodeParser
                        
                        settings = get_settings()
                        parser = SimpleNodeParser.from_defaults()
                        nodes = parser.get_nodes_from_documents([Document(text=text)])
                        
                        # Add metadata to nodes
                        for node in nodes:
                            node.metadata = {
                                "course_name": course_name,
                                "week_number": week_number,
                                "transcript_name": transcript_name
                            }
                        
                        # Store in Pinecone
                        pinecone_index = pc.Index(pinecone_index_name)
                        vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
                        index = VectorStoreIndex.from_vector_store(
                            vector_store,
                            embed_model=settings.embed_model
                        )
                        
                        # Add nodes to index
                        index.insert_nodes(nodes)
                        st.success(f"Transcript indexed in Pinecone successfully!")
                    except Exception as index_error:
                        st.warning(f"Note: Could not index to Pinecone: {str(index_error)}")
                        st.warning("This is not critical - you can still use the summarize and question functions.")
                    
                    st.success(f"Transcript uploaded and processed successfully!")
                    
                    # Add a refresh button to see the new upload in other tabs
                    if st.button("Refresh App"):
                        st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

with tab2:
    st.header("Summarize Transcripts")
    
    # Get available courses
    courses = []
    if apis_configured:
        try:
            response = supabase.table("transcripts").select("course_name").execute()
            courses = list(set([item["course_name"] for item in response.data]))
        except Exception as e:
            st.error(f"Error fetching courses: {str(e)}")
    
    selected_course = st.selectbox("Select Course", courses if courses else ["No courses available"])
    
    if selected_course != "No courses available":
        # Get weeks for selected course
        weeks = []
        try:
            response = supabase.table("transcripts").select("week_number").eq("course_name", selected_course).execute()
            weeks = sorted(list(set([item["week_number"] for item in response.data])))
        except Exception as e:
            st.error(f"Error fetching weeks: {str(e)}")
        
        selected_week = st.selectbox("Select Week", weeks if weeks else [])
        
        if selected_week and st.button("Generate Summary"):
            with st.spinner("Generating summary..."):
                try:
                    # Fetch transcripts for the selected course and week
                    response = supabase.table("transcripts").select("*").eq("course_name", selected_course).eq("week_number", selected_week).execute()
                    if not response.data:
                        st.warning("No transcripts found for the selected course and week.")
                    else:
                        # Try to process files directly from Supabase storage
                        st.info(f"Found {len(response.data)} transcript(s) for {selected_course}, Week {selected_week}")
                        
                        # Process each transcript
                        all_text = ""
                        for transcript in response.data:
                            file_path = transcript["file_path"]
                            st.write(f"Processing {file_path}...")
                            
                            # Extract text from the PDF
                            text = extract_text_from_supabase_pdf(file_path)
                            if text:
                                all_text += text + "\n\n"
                                
                                # Index this content
                                from llama_index.core import Document
                                from llama_index.core.node_parser import SimpleNodeParser
                                
                                settings = get_settings()
                                parser = SimpleNodeParser.from_defaults()
                                nodes = parser.get_nodes_from_documents([Document(text=text)])
                                
                                # Add metadata to nodes
                                for node in nodes:
                                    node.metadata = {
                                        "course_name": selected_course,
                                        "week_number": selected_week,
                                        "transcript_name": transcript["transcript_name"]
                                    }
                                
                                # Index to Pinecone
                                try:
                                    pinecone_index = pc.Index(pinecone_index_name)
                                    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
                                    index = VectorStoreIndex.from_vector_store(
                                        vector_store,
                                        embed_model=settings.embed_model
                                    )
                                    # Add nodes to index
                                    index.insert_nodes(nodes)
                                    st.success(f"Indexed content from {file_path}")
                                except Exception as index_error:
                                    st.error(f"Error indexing to Pinecone: {str(index_error)}")
                            else:
                                st.warning(f"Could not extract text from {file_path}")
                        
                        if all_text:
                            # Generate summary using OpenAI directly
                            try:
                                # If all_text is too long, truncate it
                                max_length = 12000  # Conservative max for a prompt
                                if len(all_text) > max_length:
                                    all_text = all_text[:max_length] + "..."
                                
                                # Generate summary using OpenAI
                                response = openai.chat.completions.create(
                                    model="gpt-3.5-turbo",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful assistant that summarizes academic content."},
                                        {"role": "user", "content": f"Generate a concise summary (250-300 words) of the following Coursera content for {selected_course}, Week {selected_week}. Focus on key concepts, important definitions, and main takeaways.\n\nCONTENT:\n{all_text}"}
                                    ],
                                    max_tokens=700
                                )
                                
                                summary = response.choices[0].message.content
                                
                                st.subheader(f"Summary for {selected_course}, Week {selected_week}")
                                st.write(summary)
                                
                                # Add download button
                                st.download_button(
                                    "Download Summary",
                                    summary,
                                    file_name=f"{selected_course}_Week{selected_week}_Summary.txt",
                                    mime="text/plain"
                                )
                            except Exception as summary_error:
                                st.error(f"Error generating summary: {str(summary_error)}")
                        else:
                            st.error("Could not extract text from any of the transcripts.")
                except Exception as e:
                    st.error(f"Error generating summary: {str(e)}")

with tab3:
    st.header("Ask Questions")
    
    # Chat history in session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Get available courses for filtering
    courses = []
    if apis_configured:
        try:
            response = supabase.table("transcripts").select("course_name").execute()
            courses = list(set([item["course_name"] for item in response.data]))
        except Exception as e:
            st.error(f"Error fetching courses: {str(e)}")
    
    # Course/week filters
    col1, col2 = st.columns(2)
    with col1:
        selected_course = st.selectbox("Filter by Course", ["All Courses"] + courses if courses else ["No courses available"], key="chat_course")
    
    weeks = []
    if selected_course not in ["All Courses", "No courses available"]:
        try:
            response = supabase.table("transcripts").select("week_number").eq("course_name", selected_course).execute()
            weeks = sorted(list(set([item["week_number"] for item in response.data])))
        except Exception as e:
            st.error(f"Error fetching weeks: {str(e)}")
    
    with col2:
        selected_week = st.selectbox("Filter by Week", ["All Weeks"] + [str(w) for w in weeks] if weeks else ["All Weeks"], key="chat_week")
    
    # Get user input
    user_query = st.chat_input("Ask about your Coursera content")
    
    if user_query:
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.write(user_query)
        
        # Generate AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Build query to get relevant files
                    query = supabase.table("transcripts").select("*")
                    
                    if selected_course != "All Courses" and selected_course != "No courses available":
                        query = query.eq("course_name", selected_course)
                    
                    if selected_week != "All Weeks":
                        query = query.eq("week_number", int(selected_week))
                    
                    response = query.execute()
                    
                    if not response.data:
                        st.warning("No transcripts found for the selected filters.")
                        ai_response = "I don't have any information for your query. Please check if you have uploaded relevant transcripts and selected the correct course/week."
                    else:
                        # Process the PDFs to extract text
                        st.info(f"Searching through {len(response.data)} transcript(s)...")
                        
                        all_text = ""
                        for transcript in response.data:
                            file_path = transcript["file_path"]
                            # Extract text from the PDF
                            text = extract_text_from_supabase_pdf(file_path)
                            if text:
                                all_text += f"\n\n--- {transcript['transcript_name']} ---\n\n{text}"
                        
                        if not all_text:
                            ai_response = "I couldn't extract text from any of the transcripts. Please check if the PDFs are valid and try again."
                        else:
                            # If content is too large, truncate
                            max_length = 14000  # Conservative max for context
                            if len(all_text) > max_length:
                                st.warning("The transcript content is very large. Only using the first portion for the response.")
                                all_text = all_text[:max_length] + "..."
                            
                            # Use OpenAI to generate response
                            response = openai.chat.completions.create(
                                model="gpt-3.5-turbo-16k",
                                messages=[
                                    {"role": "system", "content": "You are a helpful assistant that answers questions about Coursera course content. Provide detailed, accurate responses based on the transcript content provided. If the answer is not in the transcripts, clearly state that."},
                                    {"role": "user", "content": f"Here is the transcript content:\n\n{all_text}\n\nBased only on this content, please answer the following question:\n{user_query}"}
                                ],
                                max_tokens=1000
                            )
                            
                            ai_response = response.choices[0].message.content
                    
                    st.write(ai_response)
                    st.session_state.messages.append({"role": "assistant", "content": ai_response})
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

with tab4:
    st.header("Generate Quiz Questions")
    
    # Get available courses
    courses = []
    if apis_configured:
        try:
            response = supabase.table("transcripts").select("course_name").execute()
            courses = list(set([item["course_name"] for item in response.data]))
        except Exception as e:
            st.error(f"Error fetching courses: {str(e)}")
    
    selected_course = st.selectbox("Select Course", courses if courses else ["No courses available"], key="quiz_course")
    
    if selected_course != "No courses available":
        # Get weeks for selected course
        weeks = []
        try:
            response = supabase.table("transcripts").select("week_number").eq("course_name", selected_course).execute()
            weeks = sorted(list(set([item["week_number"] for item in response.data])))
        except Exception as e:
            st.error(f"Error fetching weeks: {str(e)}")
        
        selected_week = st.selectbox("Select Week", weeks if weeks else [], key="quiz_week")
        
        question_types = st.multiselect(
            "Question Types", 
            ["Multiple Choice", "True/False", "Short Answer"],
            default=["Multiple Choice", "True/False"]
        )
        
        num_questions = st.slider("Number of Questions", 3, 10, 5)
        
        if selected_week and st.button("Generate Quiz"):
            with st.spinner("Generating quiz questions..."):
                try:
                    # Build the prompt
                    question_types_str = ", ".join(question_types)
                    
                    # Query with RAG
                    index = get_vector_index()
                    query_engine = index.as_query_engine(
                        similarity_top_k=10,
                        filters={
                            "course_name": {"$eq": selected_course},
                            "week_number": {"$eq": selected_week}
                        }
                    )
                    
                    prompt = f"""Generate {num_questions} quiz questions from the Coursera course '{selected_course}', Week {selected_week}.
                    Include the following question types: {question_types_str}.
                    For each question:
                    1. Provide the question clearly
                    2. For multiple-choice, include 4 options (A, B, C, D) with only one correct answer
                    3. For all questions, provide the correct answer
                    4. Include a brief explanation of why the answer is correct, referencing the course content
                    
                    Format each question with a number, followed by the question type in parentheses.
                    """
                    
                    response = query_engine.query(prompt)
                    
                    st.subheader(f"Quiz Questions for {selected_course}, Week {selected_week}")
                    st.write(response.response)
                    
                    # Add download button for the quiz
                    st.download_button(
                        "Download Quiz",
                        response.response,
                        file_name=f"{selected_course}_Week{selected_week}_Quiz.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Error generating quiz: {str(e)}")

with tab5:
    st.header("Exam Preparation")
    
    # Get available courses
    courses = []
    if apis_configured:
        try:
            response = supabase.table("transcripts").select("course_name").execute()
            courses = list(set([item["course_name"] for item in response.data]))
        except Exception as e:
            st.error(f"Error fetching courses: {str(e)}")
    
    selected_course = st.selectbox("Select Course", courses if courses else ["No courses available"], key="exam_course")
    
    if selected_course != "No courses available":
        col1, col2 = st.columns(2)
        
        with col1:
            exam_format = st.radio(
                "Exam Format",
                ["Comprehensive (all weeks)", "Specific weeks"]
            )
        
        selected_weeks = []
        if exam_format == "Specific weeks":
            # Get weeks for selected course
            weeks = []
            try:
                response = supabase.table("transcripts").select("week_number").eq("course_name", selected_course).execute()
                weeks = sorted(list(set([item["week_number"] for item in response.data])))
            except Exception as e:
                st.error(f"Error fetching weeks: {str(e)}")
            
            with col2:
                selected_weeks = st.multiselect("Select Weeks", weeks if weeks else [])
        
        num_questions = st.slider("Number of Questions", 5, 20, 10, key="exam_questions")
        
        difficulty = st.select_slider(
            "Difficulty Level",
            options=["Easy", "Medium", "Hard"],
            value="Medium"
        )
        
        if st.button("Generate Practice Exam"):
            with st.spinner("Generating practice exam..."):
                try:
                    # Build the prompt and filters
                    filters = {"course_name": {"$eq": selected_course}}
                    
                    if exam_format == "Specific weeks" and selected_weeks:
                        # Create a string of weeks for the prompt
                        weeks_str = ", ".join([str(w) for w in selected_weeks])
                        prompt_weeks = f"Weeks {weeks_str}"
                        
                        # For filtering, we need to use $in operator
                        filters["week_number"] = {"$in": selected_weeks}
                    else:
                        prompt_weeks = "all weeks"
                    
                    # Query with RAG
                    index = get_vector_index()
                    query_engine = index.as_query_engine(
                        similarity_top_k=15,
                        filters=filters
                    )
                    
                    prompt = f"""Create a practice exam for the Coursera course '{selected_course}', covering {prompt_weeks}.
                    Generate {num_questions} questions at {difficulty} difficulty level.
                    
                    Include a mix of:
                    - Multiple-choice questions (4 options)
                    - True/False questions
                    - Short answer questions
                    
                    For each question:
                    1. Clearly state the question
                    2. Provide all necessary options for multiple-choice
                    3. Include the correct answer
                    4. Provide a detailed explanation of the answer, referencing specific course content
                    
                    The exam should resemble an actual Coursera exam in style and format.
                    Number each question and specify its type in parentheses.
                    """
                    
                    response = query_engine.query(prompt)
                    
                    st.subheader(f"Practice Exam for {selected_course}")
                    st.write(response.response)
                    
                    # Add download button for the exam
                    st.download_button(
                        "Download Practice Exam",
                        response.response,
                        file_name=f"{selected_course}_PracticeExam.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"Error generating practice exam: {str(e)}")

# Footer
st.sidebar.markdown("---")
st.sidebar.info("Made with Streamlit, LlamaIndex, and OpenAI")

# API configuration instructions if not set up
if not apis_configured:
    st.warning("""
    ### API Configuration Required
    
    Please set up your API keys in a `.env` file or Streamlit secrets:
    
    ```
    OPENAI_API_KEY=your-openai-api-key
    SUPABASE_URL=your-supabase-url
    SUPABASE_KEY=your-supabase-key
    PINECONE_API_KEY=your-pinecone-api-key
    PINECONE_ENVIRONMENT=gcp-starter
    ```
    
    See the README for setup instructions.
    """) 