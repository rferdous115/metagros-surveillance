# Metagros — AI Video Surveillance Platform

**See More. Know More.**

---

## 💡 Inspiration

Security teams spend hours scrubbing through CCTV footage looking for 30-second clips. Traditional surveillance is reactive—incidents are reviewed *after* they happen, often too late.

We built Metagros to flip the script: **cameras that understand what they see, not just record pixels.**

With multimodal AI like Twelve Labs, we can finally search video the same way we search text: *"person leaving a bag unattended"* → instant timestamped results.

---

## 🎯 What it does

Metagros is a desktop AI surveillance platform with four core modules:

### 1. **Live Surveillance**
- Real-time webcam feeds
- On-device face detection (optional)

### 2. **Video Analysis (AI)**
- Upload footage and index with **Twelve Labs Pegasus**
- Search using natural language: *"person tailgating through door"*
- Get timestamped evidence clips with confidence scores
- Generate **court-ready PDF reports** with timeline and recommended actions

### 3. **CCTV Grid (Multi-Camera)**
- Manage 4+ camera feeds in a dynamic grid
- Real-time **YOLOv8 object detection** (person, vehicle, etc.)
- Behavioral alerts: loitering (15+ sec), crowd gathering
- **Deep Analyze**: capture 5-sec clip → Twelve Labs instant AI analysis

### 4. **Settings**
- Secure login with salted SHA-256 password hashing
- Change password, logout functionality

---

## 🛠️ How we built it

| Component | Technology |
|-----------|------------|
| **Language** | Python 3.x |
| **UI Framework** | PySide6 (Qt) |
| **Local AI** | Ultralytics YOLOv8 |
| **Cloud AI** | Twelve Labs (Pegasus) |
| **Video Processing** | OpenCV |
| **Database** | SQLite |
| **Icons** | QtAwesome (Font Awesome) |
| **Notifications** | Windows Toast (winotify) |
| **Reports** | ReportLab (PDF) |

### Architecture
```
User Interface (Qt)
    ├─ Live Tab → Camera + Face Detection
    ├─ Video AI Tab → TwelveLabs Client → Incident Reports
    ├─ Grid Tab → Multi-Camera + YOLO + Person Tracker
    └─ Settings → Auth Manager (SQLite)
```

### Key Features
- **Async operations**: Long AI tasks run on `QThread` workers to prevent UI freezing
- **Behavior tracking**: Person/vehicle trackers identify loitering using bounding box motion history
- **Query expansion**: Each incident type (Tailgating, Loitering, etc.) expands into 5+ semantic queries
- **Evidence merging**: Overlapping clips within 2 seconds are merged and trimmed to 15-sec max

---

## 🚧 Challenges we ran into

1. **UI Freezing** — Twelve Labs API calls blocked Qt event loop → refactored to `QThread` workers
2. **Git Bloat** — Accidentally committed 1.2GB `venv/` → nuked history and rewrote `.gitignore`
3. **Timestamp Parsing** — API returned `mm:ss`, plain seconds, and freeform text → built flexible `parse_time()` helper
4. **Dependency Hell** — `face_recognition` requires `dlib` + CMake on Windows → made it optional
5. **YOLO Spam** — Same person detected 30x/sec → added cooldowns, deduplication, and tracking-based alerts

---

## 🏆 Accomplishments that we're proud of

✅ **End-to-end incident workflow** — Upload → Search → Report in one seamless app  
✅ **Natural language search** — "person lingering near exit" → timestamped clips  
✅ **Real-time behavior AI** — Tracks individuals across frames, alerts on 15+ sec loitering  
✅ **Professional UI** — Dark theme, sharp corners, qtawesome icons (no emojis)  
✅ **Secure by default** — No hardcoded APIs, salted password hashing, offline-first

---

## 📚 What we learned

- **Qt threading is tricky** — Can't touch UI from worker threads; must use signals
- **AI output is messy** — LLMs don't always follow formats; robust regex + fallbacks essential
- **Video is compute-heavy** — 30 FPS frame processing requires careful optimization
- **Developer experience matters** — Clean `.gitignore`, modular code, and env vars save headaches

---

## 🚀 What's next for Metagros

### Short Term
- [ ] Build standalone Windows `.exe` with PyInstaller
- [ ] Add **Edge Node Status** widget (CPU/GPU/RAM graphs)
- [ ] Custom frameless window for sleeker UI

### Medium Term
- [ ] **Geospatial Map** — Plot cameras on floor plan, visualize event clusters
- [ ] **Cross-Camera Face Search** — "Find where this person went"
- [ ] **Audio Intelligence** — Detect gunshots, screams, glass breaking

### Long Term
- [ ] **Mobile App** — Push notifications with video clips
- [ ] **Cloud Dashboard** — Multi-site encrypted sync
- [ ] **Federated Learning** — Improve models without sharing raw footage

---

## 🧰 Tech Stack Summary

**Languages**: Python  
**Frameworks**: PySide6, OpenCV, Ultralytics  
**Platforms**: Windows 10/11  
**Cloud Services**: Twelve Labs (Pegasus API)  
**Databases**: SQLite  
**APIs**: Twelve Labs Video Understanding API  
**Other**: QtAwesome, ReportLab, Windows Toast Notifications

---

**Built for the future of intelligent surveillance.**
