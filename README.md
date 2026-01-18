# Metagros — AI Video Surveillance Platform

**See More. Know More.**

A desktop surveillance application combining real-time YOLO object detection with Twelve Labs cloud video AI for intelligent incident investigation.

---

## Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.10, 3.11)
- **Windows 10/11** (for desktop notifications)
- **Webcam** (for live CCTV features)
- **Twelve Labs API Key** — [Get one free](https://twelvelabs.io/)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/rferdous115/metagros-surveillance.git
   cd metagros-surveillance
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate virtual environment**
   ```powershell
   # Windows PowerShell
   .\venv\Scripts\Activate.ps1
   
   # Windows CMD
   .\venv\Scripts\activate.bat
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set your Twelve Labs API key**
   ```powershell
   # PowerShell (temporary, for current session)
   $env:TWELVE_LABS_API_KEY="your_api_key_here"
   
   # Or permanently in System Environment Variables
   ```

### Running the App

```powershell
python qt_app.py
```

**Default Login:**
- Username: `admin`
- Password: `metagros`

---

## Features

### Video Analysis (AI) Tab
- Upload video files for cloud indexing
- Natural language search: *"person leaving a bag unattended"*
- Timestamped evidence clips with confidence scores
- PDF incident report generation

### CCTV Grid Tab
- Multi-camera management (2x2, 3x3, 4x4 grids)
- Real-time YOLOv8 object detection (person, vehicle, etc.)
- Loitering detection (15+ seconds in same area)
- Crowd gathering alerts
- Deep Analyze: 5-second clip → Twelve Labs AI analysis

### Settings Tab
- Change password
- Logout

---

## Project Structure

```
metagros-surveillance/
├── qt_app.py              # Main application entry point
├── twelvelabs_client.py   # Twelve Labs API wrapper
├── multi_camera.py        # Multi-camera manager with YOLO
├── person_tracker.py      # Loitering/behavior detection
├── incident_workflow.py   # Query expansion & report generation
├── pdf_report.py          # PDF report generation
├── auth_manager.py        # SQLite user authentication
├── requirements.txt       # Python dependencies
├── yolov8n.pt            # YOLOv8 nano model weights
└── .gitignore            # Git ignore rules
```

---

## Dependencies

```
PySide6          # Qt GUI framework
opencv-python    # Video processing
ultralytics      # YOLOv8 object detection
twelvelabs       # Twelve Labs SDK
qtawesome        # Font Awesome icons
reportlab        # PDF generation
```

Install all with: `pip install -r requirements.txt`

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'X'"
```bash
pip install X
```

### "face_recognition not installed" warning
This is optional. Face detection is disabled but the app works fine without it.

### Webcam not working
- Ensure no other app is using the webcam
- Check Windows Camera permissions

### Twelve Labs errors
- Verify your API key is set correctly
- Check your internet connection
- Ensure you have API quota remaining

---

## Building Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Build
.\build_exe.bat
```

Output: `dist/Metagros.exe`

---

## License

MIT License

---

**Built for the future of intelligent surveillance.**
