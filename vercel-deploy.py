import streamlit as st
import subprocess
import os
import sys

# Import the main app
from app import *

if __name__ == "__main__":
    # Run the Streamlit app
    st._main_run_cloned = True
    sys.argv = ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
    sys.exit(st._main_run()) 