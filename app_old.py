import streamlit as st
import os
from dotenv import load_dotenv
import openai
from supabase import create_client
import pinecone
from llama_index.core import VectorStoreIndex, ServiceContext
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
import fitz  # PyMuPDF
import tempfile
import uuid

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
    supabase = create_client(supabase_url, supabase_key)
    
    # Pinecone
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")
    pinecone_env = os.environ.get("PINECONE_ENVIRONMENT", "gcp-starter")
    if not pinecone_api_key:
        pinecone_api_key = st.secrets.get("PINECONE_API_KEY")
    pinecone.init(api_key=pinecone_api_key, environment=pinecone_env)
    pinecone_index_name = "coursera-transcripts"
    
    apis_configured = True
except Exception as e:
    st.error(f"Error initializing APIs: {str(e)}")
    apis_configured = False

# Create sidebar
st.sidebar.title("Coursera Study Buddy")
st.sidebar.info("Upload Coursera transcripts and interact with them using AI.")

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

def get_service_context():
    embed_model = OpenAIEmbedding()
    llm = OpenAI(model="gpt-3.5-turbo", temperature=0.1)
    return ServiceContext.from_defaults(llm=llm, embed_model=embed_model)

def get_vector_index():
    pinecone_index = pinecone.Index(pinecone_index_name)
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
    service_context = get_service_context()
    return VectorStoreIndex.from_vector_store(
        vector_store,
        service_context=service_context
    )

# Main application logic for each tab
with tab1:
    st.header("Upload Coursera Transcripts")
    
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
                    # Save file to Supabase
                    file_path = f"transcripts/{course_name}/{week_number}/{uploaded_file.name}"
                    supabase.storage.from_("transcripts").upload(
                        file_path,
                        uploaded_file.getvalue(),
                        {"content-type": "application/pdf"}
                    )
                    
                    # Save metadata to Supabase
                    supabase.table("transcripts").insert({
                        "course_name": course_name,
                        "week_number": week_number,
                        "transcript_name": transcript_name,
                        "file_path": file_path
                    }).execute()
                    
                    # Index transcript in Pinecone
                    from llama_index.core import Document
                    from llama_index.core.node_parser import SimpleNodeParser
                    
                    service_context = get_service_context()
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
                    pinecone_index = pinecone.Index(pinecone_index_name)
                    vector_store = PineconeVectorStore(pinecone_index=pinecone_index)
                    index = VectorStoreIndex.from_vector_store(
                        vector_store,
                        service_context=service_context
                    )
                    
                    st.success(f"Transcript uploaded and indexed successfully!")
                    
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
                        # Query with RAG
                        index = get_vector_index()
                        query_engine = index.as_query_engine(
                            similarity_top_k=5,
                            filters={
                                "course_name": {"$eq": selected_course},
                                "week_number": {"$eq": selected_week}
                            }
                        )
                        
                        prompt = f"Generate a concise summary (250-300 words) of the following Coursera content for {selected_course}, Week {selected_week}. Focus on key concepts, important definitions, and main takeaways."
                        response = query_engine.query(prompt)
                        
                        st.subheader(f"Summary for {selected_course}, Week {selected_week}")
                        st.write(response.response)
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
                    # Build filters
                    filters = {}
                    if selected_course != "All Courses" and selected_course != "No courses available":
                        filters["course_name"] = {"$eq": selected_course}
                    if selected_week != "All Weeks":
                        filters["week_number"] = {"$eq": int(selected_week)}
                    
                    # Query with RAG
                    index = get_vector_index()
                    query_engine = index.as_query_engine(
                        similarity_top_k=5,
                        filters=filters if filters else None
                    )
                    
                    response = query_engine.query(user_query)
                    ai_response = response.response
                    
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