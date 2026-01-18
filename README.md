### How to Run Metagros

1. Clone the repository git clone https://github.com/rferdous115/metagros-surveillance.git cd metagros-surveillance
2. Create and activate virtual environment python -m venv venv .\venv\Scripts\Activate.ps1
3. Install dependencies pip install -r requirements.txt
4. Set your Twelve Labs API key $env:TWELVE_LABS_API_KEY="your_api_key_here"5
5. Run the application python qt_app.py
6. Login with default credentials Username: admin Password: metagros

### How to Use

#### Video Analysis (AI) order of operations
1. Click "Open Video" to load a video file
2. Use the slider to preview the video content
3. Click "Index with Twelvelabs" to upload and index the video (wait for "Ready for analysis!")
4. Select an incident type from the dropdown (e.g., Loitering, Tailgating) OR type a custom query5
5. Set sensitivity level (Low/Medium/High)
6. Click "Detect Incidents" to search for matching moments
7. Review evidence clips in the table — check/uncheck clips to include
8. Fill in Location and Camera ID fields
9. Click "Generate Report" for AI-powered incident summary
10. Export as PDF or JSON using the export buttons

#### CCTV Grid Tab order of operations
1. Click "Webcam" to add your laptop camera to the grid
2. (Optional) Click "Add Demo Cam" for testing or enter RTSP URL for IP cameras
3. Select a detection scenario from dropdown (e.g., Person Loitering)
4. Enter a detection prompt describing what to look for
5. Click "Add Rule" to create the detection rule
6. Click "Start Monitoring" to begin real-time AI detection
7. Watch the "Detected Events" console for alerts
8. Click "Deep Analyze" to capture 5 seconds and send to Twelve Labs for detailed AI analysis
9. Click "Stop Monitoring" when done
10. Click camera tiles to select/highlight them

#### Settings Tab order of operations
1. To change password: Enter current password, then new password twice
2. Click "Change Password" to update credentials

1. Click "Logout" to return to login screen
