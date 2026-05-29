  Step 1: Install Python        



  1. Open your web browser and go to: python.org/downloads

  2. Click the big yellow button "Download Python 3.12.x"

  3. Open the downloaded file

  4. IMPORTANT: On the first screen, check the box that says "Add Python

   to PATH" at the bottom

  5. Click "Install Now"

  6. Wait for installation to complete, then click "Close"



  Verify Python is installed:   



  1. Press Windows key + R on your keyboard

  2. Type cmd and press Enter (this opens Command Prompt)

  3. Type this and press Enter:

  python --version

  4. You should see something like Python 3.12.x — if yes, move to Step

  2



  ---

  Step 2: Download the Project

                                

  Option A: From GitHub



  1. Go to the GitHub repository link shared with you

  2. Click the green "Code" button

  3. Click "Download ZIP"

  4. Open your Downloads folder

  5. Right-click the ZIP file → "Extract All" → Choose Desktop → Click

  "Extract"



  Option B: From ZIP file shared via email/drive

  

  1. Save the ZIP file to your Desktop

  2. Right-click it → "Extract All" → Click "Extract"



  You should now have a folder on your Desktop called

  OBERON-301-Clinical-Review    



  ---

  Step 3: Get an OpenAI API Key 

  

  1. Go to platform.openai.com and sign up / log in

  2. Click your profile icon (top right) → "API keys"

  3. Click "Create new secret key"

  4. Copy the key (starts with sk-...) — save it somewhere safe, you'll 

  need it soon



  ▎ Note: OpenAI charges per API call. One full analysis run costs 

  ▎ approximately $1.50–$2.00. You can also run the app in "Rules Only" 

  ▎ mode for free (no API key needed).

  

  ---                           

  Step 4: Set Up the App

  

  1. Open Command Prompt:

    - Press Windows key + R

    - Type cmd and press Enter

  2. Navigate to the project folder (copy-paste each line and press

  Enter):

  cd Desktop\OBERON-301-Clinical-Review

  3. Create a virtual environment:

  python -m venv venv

  4. Activate the virtual environment:

  venv\Scripts\activate

  4. You should see (venv) appear at the beginning of the line

  5. Install required packages:

  pip install -r requirements.txt

  5. Wait for it to finish (may take 1–2 minutes)

  6. Create the configuration file:

  copy .env.example .env        

  7. Open the .env file to add your API key:

  notepad .env

  8. In Notepad, find the line that says:

  OPENAI_API_KEY=your_key_here

  8. Replace your_key_here with your actual API key (the sk-... key from

   Step 3)

  9. Save the file (Ctrl + S) and close Notepad



  ---

  Step 5: Start the App         

  

  1. In the same Command Prompt window (make sure you still see (venv)),

   type:

  python -m uvicorn app:app --host 0.0.0.0 --port 8000

  2. You should see:

  INFO:     Uvicorn running on http://0.0.0.0:8000

  3. Open your web browser (Chrome, Edge, etc.)

  4. Go to: http://localhost:8000



  ▎ The app is now running! Keep the Command Prompt window open — 

  ▎ closing it will stop the app.



  ---

  Step 6: Using the App         

  

  Upload Data



  1. On the upload screen, click "Choose Files" or drag and drop

  2. Select all 7 CSV files from the data folder inside the project:

    - Demographics.csv

    - Medical_History.csv       

    - Concomitant_Meds.csv

    - Adverse_Events.csv

    - Lab_Data.csv

    - Vital_Signs.csv

    - Disposition.csv

  

  Run Analysis                  



  1. Select the LLM provider:

    - Rules Only — free, instant results (~104 flags), no API key needed

    - OpenAI — uses GPT-4o, takes 5–10 minutes, costs ~$1.50 per run

  2. Click "Run Analysis"

  3. Wait for the progress bar to complete



  View Results 



  - Summary page — total flags, severity breakdown

  - Flags table — sortable, filterable list of all issues found

  - Subject detail — click any Subject ID for full profile view

  - Export — click the Export button to download results as CSV



  ---

  Everyday Usage (After Initial Setup)

  

  Each time you want to use the app:



  1. Open Command Prompt (Windows key + R → type cmd → Enter)

  2. Run these commands:

  cd Desktop\OBERON-301-Clinical-Review

  venv\Scripts\activate

  python -m uvicorn app:app --host 0.0.0.0 --port 8000

  3. Open browser → go to http://localhost:8000

  4. When done, close the Command Prompt window

  

  ---

  Troubleshooting



  ┌─────────────────────────┬───────────────────────────────────────┐

  │         Problem         │               Solution                │

  ├─────────────────────────┼───────────────────────────────────────┤

  │ python not recognized   │ Reinstall Python and make sure to     │

  │                         │ check "Add to PATH"                   │

  ├─────────────────────────┼───────────────────────────────────────┤

  │                         │ Try: Set-ExecutionPolicy -Scope       │

  │ venv\Scripts\activate   │ CurrentUser -ExecutionPolicy          │

  │ gives error             │ RemoteSigned in PowerShell, then      │

  │ use                     │ app:app --port 8001 then go to        │

  │                         │ http://localhost:8001                 │

  ├─────────────────────────┼───────────────────────────────────────┤

  │                         │ Check your API key in the .env file.  │

  │ LLM analysis fails      │ Make sure you have credits on your    │

  Each time you want to use the app:



  1. Open Command Prompt (Windows key + R → type cmd → Enter)

  2. Run these commands:

  cd Desktop\OBERON-301-Clinical-Review

  venv\Scripts\activate

  python -m uvicorn app:app --host 0.0.0.0 --port 8000

  3. Open browser → go to http://localhost:8000

  4. When done, close the Command Prompt window



  ---

  Troubleshooting



  ┌────────────────────────────┬─────────────────────────────────────────────────────────┐

  │          Problem           │                        Solution                         │

  ├────────────────────────────┼─────────────────────────────────────────────────────────┤

  │ python not recognized      │ Reinstall Python and make sure to check "Add to PATH"   │

  ├────────────────────────────┼─────────────────────────────────────────────────────────┤

  │ venv\Scripts\activate      │ Try: Set-ExecutionPolicy -Scope CurrentUser             │

  │ gives error                │ -ExecutionPolicy RemoteSigned in PowerShell, then retry │

  ├────────────────────────────┼─────────────────────────────────────────────────────────┤

  │ Port 8000 already in use   │ Change the port: python -m uvicorn app:app --port 8001  │

  │                            │ then go to http://localhost:8001                        │

  ├───────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤

  │ Port 8000 already in use          │ Change the port: python -m uvicorn app:app --port 8001 then go to http://localhost:8001             │

  ├───────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤

  │ LLM analysis fails                │ Check your API key in the .env file. Make sure you have credits on your OpenAI account              │

  ├───────────────────────────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────────┤

  │ App shows blank page              │ Clear browser cache (Ctrl + Shift + Delete) and refresh                                             │

  └───────────────────────────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────────┘

