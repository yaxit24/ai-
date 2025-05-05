import subprocess
import os
import sys

# Install dependencies
subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements-vercel.txt"])

# Run Streamlit app
def app():
    return subprocess.Popen(["streamlit", "run", "app.py", "--server.port", "8080", "--server.address", "0.0.0.0"])

if __name__ == "__main__":
    app() 