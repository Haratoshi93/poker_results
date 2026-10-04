@echo off
chcp 65001 > nul

echo [INFO] Creating virtual environment...
py -m venv venv

echo [INFO] Activating virtual environment and installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt

echo [INFO] Starting Streamlit app...
echo [INFO] Press Ctrl+C in this window to stop the server.
streamlit run app.py

pause
