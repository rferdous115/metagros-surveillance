# Metagros AI Surveillance Platform

> **Intelligent video surveillance that understands what it sees.**

---

## Inspiration

Traditional CCTV systems generate terabytes of footage that no one has time to watch. Security teams are reactive—reviewing footage *after* incidents occur, spending hours scrubbing through recordings to find a 30-second clip.

We asked: **What if cameras could understand context, not just capture pixels?**

The rise of multimodal AI—specifically Twelve Labs' video understanding API—made this vision achievable. We wanted to build a desktop surveillance platform that combines:

1. **Real-time local detection** (edge AI for instant alerts)
2. **Deep semantic search** (describe what you're looking for in plain English)
3. **Structured incident reporting** (court-ready documentation with timestamps)

The goal was a tool that security professionals would actually want to use—not another clunky NVR interface.

---

## What It Does

Metagros is a **desktop AI surveillance platform** built with Python and PySide6. It offers:

### 🎥 Live Surveillance Tab
- Webcam integration with real-time feed display
- Class management for custom detection categories

### 📹 Video Analysis (AI) Tab
- **Video upload and indexing** with Twelve Labs Pegasus model
- **Incident detection** using 7 preset incident types (Unauthorized Access, Tailgating, Loitering, Fight/Assault, etc.)
- **Custom natural language queries** — "person leaving a bag and walking away"
- **Evidence clip extraction** with start/end timestamps, confidence scores
- **Incident report generation** with executive summary, timeline, and recommended actions
- **PDF export** for court-ready documentation

### 📡 CCTV Grid Tab
- **Multi-camera management** with clickable, resizable grid
- **YOLO v8 object detection** running locally (person, vehicle, etc.)
- **Behavior detection** for loitering (person staying in same area 15+ seconds) and crowd gathering
- **Deep Analyze** — capture 5-second clip and send to Twelve Labs for detailed AI analysis
- **Rule-based alerting** with Windows toast notifications

### ⚙️ Settings Tab
- **Secure authentication** with salted SHA-256 password hashing
- **Change password** functionality
- **Logout** to return to login screen

---

## How We Built It

### Tech Stack

| Layer | Technology |
|-------|------------|
| **UI Framework** | PySide6 (Qt for Python) |
| **AI - Local** | Ultralytics YOLOv8 (object detection) |
| **AI - Cloud** | Twelve Labs Marengo/Pegasus (video understanding) |
| **Database** | SQLite (user authentication) |
| **Icons** | QtAwesome (Font Awesome icons) |
| **Video** | OpenCV (capture, processing, display) |
| **Notifications** | Windows Toast (winotify) |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      PySide6 Qt UI                          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Live    │  │Video Analysis│  │ CCTV Grid│  │Settings │ │
│  │Surveil.  │  │    (AI)      │  │ (Multi)  │  │         │ │
│  └────┬─────┘  └──────┬───────┘  └────┬─────┘  └────┬────┘ │
│       │               │               │              │      │
│       ▼               ▼               ▼              ▼      │
│  ┌────────┐    ┌───────────┐   ┌──────────┐   ┌─────────┐  │
│  │Camera  │    │TwelveLabs │   │MultiCam  │   │AuthMgr  │  │
│  │Handler │    │  Client   │   │ Manager  │   │(SQLite) │  │
│  └────────┘    └───────────┘   └────┬─────┘   └─────────┘  │
│                                     │                       │
│                              ┌──────┴──────┐               │
│                              │ YOLO v8     │               │
│                              │ Detector    │               │
│                              └─────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### Key Modules

| File | Purpose | Lines |
|------|---------|-------|
| `qt_app.py` | Main UI application with all tabs | ~2300 |
| `incident_workflow.py` | Query expansion, moment merging, report generation | 378 |
| `twelvelabs_client.py` | Twelve Labs API wrapper | 300+ |
| `multi_camera.py` | Multi-camera management with YOLO | 150 |
| `person_tracker.py` | Loitering and behavior detection | 300 |
| `auth_manager.py` | Secure user authentication | 100 |
| `pdf_report.py` | Court-ready PDF report generation | 250 |

---

## Challenges We Ran Into

### 1. **UI Freezing During AI Operations**
Long-running Twelve Labs API calls were blocking the Qt event loop. We refactored all AI operations (`DeepAnalyzeWorker`, `IncidentDetectionWorker`, `UploadWorker`) into `QThread` workers with signal-based progress updates.

### 2. **Virtual Environment Git Bloat**
The repository ballooned to 1.2GB when `venv/` was accidentally committed. We had to nuke the Git history and reinitialize with a robust `.gitignore` to exclude Python environments, build artifacts, and model weights.

### 3. **Timestamp Parsing Mismatch**
Twelve Labs returns timestamps in various formats (`mm:ss`, plain seconds, or embedded in text). We implemented a flexible `parse_time()` function that handles all formats and falls back gracefully.

### 4. **Face Recognition Dependency Hell**
The `face_recognition` library requires `dlib`, which requires CMake and Visual Studio Build Tools on Windows. We made it optional—the app runs without face detection if the dependency isn't installed.

### 5. **YOLO Detection Spam**
YOLO was detecting the same person every frame, flooding the UI with alerts. We added:
- Detection cooldowns per rule
- Deduplication based on bounding box overlap
- Tracking-based alerts (only alert when behavior *starts*)

---

## Accomplishments We're Proud Of

### ✅ **End-to-End Incident Workflow**
From uploading a video to generating a PDF report with evidence clips, timestamps, and recommended actions—all in one application.

### ✅ **Natural Language Search**
Users can type "person lingering near emergency exit" and get timestamped results. No ML expertise required.

### ✅ **Real-Time Behavior Detection**
Loitering detection tracks individual persons across frames and alerts when someone stays in the same area for 15+ seconds.

### ✅ **Professional UI Design**
Dark theme, sharp corners (2px radius), qtawesome icons, and a layout inspired by enterprise security tools like Palantir and Genetec.

### ✅ **Secure by Default**
- Passwords are salted and hashed (SHA-256)
- API keys loaded from environment variables
- No hardcoded credentials

### ✅ **Offline-First Architecture**
Live detection runs entirely on-device. Cloud AI is only used when explicitly requested (Deep Analyze, Video Indexing).

---

## What We Learned

1. **Qt Threading is Non-Trivial** — Can't update UI from worker threads; must use signals.

2. **AI Output is Unpredictable** — LLM responses don't always follow structured formats. Robust parsing with regex fallbacks is essential.

3. **Developer Experience Matters** — Good `.gitignore`, clear module separation, and environment variables make collaboration easier.

4. **Users Want Speed** — 500ms UI lag is noticeable. Async everything.

5. **Video is Compute-Heavy** — Reading frames, resizing, encoding, and displaying at 30 FPS requires careful optimization.

---

## What's Next for Metagros

### Short Term (Next Sprint)
- [ ] **Build standalone executable** with PyInstaller
- [ ] **Add "Edge Node Status" widget** — CPU/GPU/RAM graphs for NVR health monitoring
- [ ] **Custom frameless window** — Remove default Windows title bar for sleeker design

### Medium Term
- [ ] **Geospatial Map Tab** — Plot camera locations on a floor plan, visualize event clusters
- [ ] **Face Search (Cross-Camera)** — "Find where this person went" across all feeds
- [ ] **Audio Intelligence** — Detect gunshots, screams, or glass breaking (when microphone is available)

### Long Term Vision
- [ ] **Mobile Companion App** — Push notifications with video thumbnails
- [ ] **Cloud Dashboard** — Encrypted sync for multi-site deployments
- [ ] **Federated Learning** — Improve detection models without sharing raw footage

---

## Completed Work Summary

| Category | Feature | Status |
|----------|---------|--------|
| **Core** | YOLO Object Detection (Person/Vehicle) | ✅ |
| **Core** | Twelve Labs "Deep Analyze" Integration | ✅ |
| **Behavior** | Loitering & Crowd Gathering Detection | ✅ |
| **UI** | "Palantir-style" Dark Theme & Branding | ✅ |
| **UI** | QtAwesome Icons (removed all emojis) | ✅ |
| **UI** | Dynamic Grid Resizing | ✅ |
| **UI** | QFormLayout for Incident Builder | ✅ |
| **UI** | Sharp 2px Corner Radius | ✅ |
| **UI** | Video Player Aspect Ratio Fix | ✅ |
| **Security** | Offline User Auth (SQLite + Hash) | ✅ |
| **Security** | API Key from Environment Variable | ✅ |
| **Security** | Change Password & Logout | ✅ |
| **Performance** | Deep Analyze on QThread | ✅ |
| **Performance** | Face Detection Made Optional | ✅ |
| **System** | Windows Toast Notifications | ✅ |
| **Incidents** | Custom Query Builder | ✅ |
| **Incidents** | Evidence Clip Extraction | ✅ |
| **Incidents** | PDF Report Export | ✅ |
| **Git** | Clean Repository Setup | ✅ |
| **Git** | Robust .gitignore | ✅ |

---

## Repository Structure

```
metagros-surveillance/
├── qt_app.py              # Main application (2300+ lines)
├── incident_workflow.py   # Query expansion & report generation
├── twelvelabs_client.py   # Twelve Labs API wrapper
├── multi_camera.py        # Multi-camera manager with YOLO
├── person_tracker.py      # Loitering & behavior tracking
├── object_detector.py     # YOLO v8 wrapper
├── auth_manager.py        # SQLite user authentication
├── pdf_report.py          # ReportLab PDF generation
├── rtstream_monitor.py    # VideoDB RTStream (optional)
├── camera.py              # Single camera wrapper
├── face_handler.py        # Face recognition (optional)
├── data_manager.py        # Class/data persistence
├── zone_manager.py        # ROI zone management
├── notifications.py       # Windows toast alerts
├── build_exe.bat          # PyInstaller build script
├── requirements.txt       # Python dependencies
├── yolov8n.pt            # YOLOv8 nano model weights
└── .gitignore            # Excludes venv, build, models
```

---

*Built with passion for security innovation.*

**Metagros AI** — *See More. Know More.*
