# Coursera Study Buddy

A web application that helps you interact with Coursera video transcripts using AI. Features include summarization, question-answering, question generation, and exam preparation.

## Features

- **Upload Coursera Transcripts**: Upload PDF transcripts from Coursera courses.
- **Generate Summaries**: Get concise summaries of course content by week.
- **Ask Questions**: Chat with an AI that answers questions based on course content.
- **Generate Quiz Questions**: Create customized quiz questions from course material.
- **Exam Preparation**: Generate practice exams tailored to course content.

## Technologies Used

- **Frontend**: Streamlit
- **Backend**: Python
- **AI/ML**: OpenAI API, LlamaIndex for RAG (Retrieval-Augmented Generation)
- **Storage**: 
  - Supabase (metadata & file storage)
  - Pinecone (vector database for embeddings)

## Setup

### Prerequisites

- Python 3.9+
- Accounts on:
  - [OpenAI](https://platform.openai.com/) (API key with credits)
  - [Supabase](https://supabase.com/) (free tier)
  - [Pinecone](https://www.pinecone.io/) (free tier)

### Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd coursera-study-buddy
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   
   Create a `.env` file in the project root with the following:
   ```
   OPENAI_API_KEY=your-openai-api-key
   SUPABASE_URL=your-supabase-url
   SUPABASE_KEY=your-supabase-key
   PINECONE_API_KEY=your-pinecone-api-key
   PINECONE_ENVIRONMENT=gcp-starter
   ```

### Supabase Setup

1. Create a new project on Supabase
2. Create a storage bucket called `transcripts`
3. Create a table called `transcripts` with the following schema:

```sql
CREATE TABLE transcripts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_name TEXT NOT NULL,
  week_number INTEGER,
  transcript_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Pinecone Setup

1. Create a new index named `coursera-transcripts`
2. Use `cosine` as the similarity metric
3. Use dimension of 1536 (for OpenAI embeddings)

## Running the Application

Start the Streamlit app:

```
streamlit run app.py
```

The application will be available at http://localhost:8501

## Usage

1. **Upload Tab**: Upload Coursera PDF transcripts with course name, week, and lecture name.
2. **Summarize Tab**: Generate summaries of uploaded transcripts by course and week.
3. **Ask Questions Tab**: Ask specific questions about course content.
4. **Generate Quiz Tab**: Create custom quiz questions based on course material.
5. **Exam Prep Tab**: Generate practice exams simulating Coursera quizzes.

## Deployment

### Streamlit Cloud (Free)

1. Push your code to GitHub
2. Sign up for [Streamlit Cloud](https://share.streamlit.io/)
3. Create a new app pointing to your GitHub repository
4. Add your environment variables in the Streamlit Cloud dashboard

## Limitations

- Free tier limits:
  - Supabase: 500MB storage (sufficient for ~50 PDF transcripts)
  - Pinecone: Limited to one index in the free tier
  - OpenAI API: Requires a paid API key (~$1-2/month for typical usage)

## Troubleshooting

### Supabase File Upload Issues

If you're experiencing issues with file uploads to Supabase:

1. **Check Supabase credentials**:
   - Verify your SUPABASE_URL and SUPABASE_KEY are correct
   - Ensure you're using the "anon" key (public) for the SUPABASE_KEY

2. **Bucket permissions**:
   - In the Supabase dashboard, go to Storage → Buckets → transcripts
   - Check that bucket policies allow uploads (RLS policies)
   - You may need to temporarily set the bucket to public during testing

3. **File path issues**:
   - If complex paths fail, try uploading directly to the root of the bucket
   - Use the "upsert" option for replacing existing files

4. **Check environment setup**:
   - For local development: Make sure `.env` file exists with correct credentials
   - For Streamlit Cloud: Ensure secrets are properly configured

5. **Debugging**:
   - Add debug print statements to view Supabase responses
   - Check the app logs for specific error messages

### Other Issues

If you experience other problems:

1. **Enable debug mode**:
   ```
   streamlit run app.py --logger.level=debug
   ```

2. **Check API rate limits**:
   - OpenAI and Pinecone have rate limits on free/starter tiers
   - Space requests out if hitting limits

3. **Large PDF files**:
   - PDF files over 10MB may cause memory issues
   - Consider splitting large transcripts

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. # Coursera Study Buddy
