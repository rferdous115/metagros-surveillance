# Metagros - Platform Roadmap

## ✅ Completed
- [x] **Core**: YOLO Object Detection (Person/Vehicle)
- [x] **Core**: Twelve Labs "Deep Analyze" Integration
- [x] **Behavior**: Loitering & Crowd Gathering Detection
- [x] **UI**: "Palantir-style" Dark Theme & Branding
- [x] **UI**: Octicon Icons Integration (removed emojis)
- [x] **Security**: Offline User Authentication (SQLite + Hash)
- [x] **System**: Desktop Notifications (Windows Toast)
- [x] **Incidents**: Custom Query Builder

#### 🚀 Immediate Priorities (Code Clean-up)
-   [x] **Performance**: Move `deep_analyze` to QThread (fix UI freeze)
-   [x] **Polish**: Remove emojis, Fix Contrast, & Add Grid Placeholders
-   [x] **Styling**: Global Dark Theme (Inputs), Sharp UI (2px), & QFormLayout
-   [x] **Layout**: Dynamic Grid Resizing & Video Player Aspect Ratio
-   [x] **Security**: Remove hardcoded `TWELVE_LABS_API_KEY` from `qt_app.py`
-   [ ] **Build**: Run `build_exe.bat` to generate standalone executable

## 🌟 "Elite" Features (Next Phase)
- [ ] **Geospatial Intelligence**: Add "Map View" tab with static/interactive location plotting.
- [ ] **System Status**: Add "Edge Node Status" widget (CPU/RAM/GPU usage graphs).
- [ ] **Audio Intelligence**: Add audio event detection (glass break, shouting) if microphone available.
- [ ] **Graph Analysis**: Visualize connections between "Person A" and "Vehicle B" (co-occurrence).
-   [ ] **Custom Title Bar**: Remove default Windows title bar for a truly custom, frameless look.

## 🔮 Advanced Upgrades (Future Roadmap)
-   [ ] **System Status Widget**: Add CPU, GPU, and RAM usage graphs to the CCTV tab (vital for NVR health).
-   [ ] **Audio Intelligence**: Detect gunshots, screams, or glass breaking using audio analysis.
-   [ ] **Face Search (Multi-Cam)**: "Find where this person went" across all active cameras.
-   [ ] **Heatmap Visualization**: Show dwell time and high-traffic areas on the camera feed.
-   [ ] **Geospatial Map**: Plot camera locations and detected events on a floorplan/map.

## 🔮 Future / Exploration
- [ ] **Cloud Sync**: Optional encrypted sync to cloud dashboard.
- [ ] **Mobile App**: Companion app for notifications.
