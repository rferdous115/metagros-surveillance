"""
PySide6 Surveillance Application with Security Incident Workflow

Features:
- Live Surveillance with face detection
- Video Analysis with Twelve Labs AI + Incident Builder
- CCTV Grid for multi-camera monitoring
"""
import sys
import os
import json
import cv2
import numpy as np
import math
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QFileDialog, QSlider, QListWidget, QListWidgetItem, 
    QLineEdit, QGridLayout, QScrollArea, QTextEdit, QProgressBar,
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QHeaderView, QSplitter, QSpinBox, QMessageBox, QDialog, QFrame, QFormLayout
)
from PySide6.QtCore import Qt, QTimer, QUrl, QThread, Signal
from PySide6.QtGui import QImage, QPixmap, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import qtawesome as qta

# Backend imports
from camera import Camera
from face_handler import FaceHandler
from data_manager import DataManager
from multi_camera import MultiCameraManager
from incident_workflow import IncidentType, IncidentWorkflow, EvidenceClip

# Twelve Labs API key
TWELVE_LABS_API_KEY = os.getenv("TWELVE_LABS_API_KEY", "")


def convert_cv_qt(cv_img):
    """Convert BGR opencv image to QPixmap"""
    rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb_image.shape
    bytes_per_line = ch * w
    qt_img = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qt_img)


def draw_faces_on_frame(frame, face_locations, face_names):
    """Draw face bounding boxes on frame"""
    for (top, right, bottom, left), name in zip(face_locations, face_names):
        color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 35), (right, bottom), color, cv2.FILLED)
        cv2.putText(frame, name, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 1)
    return frame


# ==================== LIVE TAB ====================
class LiveTab(QWidget):
    def __init__(self, face_handler, data_manager):
        super().__init__()
        self.face_handler = face_handler
        self.data_manager = data_manager
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.is_running = False
        self.last_locations = []
        self.last_names = []
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        
        self.video_label = QLabel("Camera Feed")
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_label, stretch=2)
        
        controls = QVBoxLayout()
        self.btn_start = QPushButton("Start Camera")
        self.btn_start.clicked.connect(self.start_camera)
        controls.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("Stop Camera")
        self.btn_stop.clicked.connect(self.stop_camera)
        self.btn_stop.setEnabled(False)
        controls.addWidget(self.btn_stop)
        
        controls.addStretch()
        controls.addWidget(QLabel("<b>Class Management</b>"))
        
        self.class_input = QLineEdit()
        self.class_input.setPlaceholderText("New Class Name")
        controls.addWidget(self.class_input)
        

        
        self.btn_add_class = QPushButton("Add Class")
        self.btn_add_class.clicked.connect(self.add_class)
        controls.addWidget(self.btn_add_class)
        
        self.class_list = QListWidget()
        self.class_list.addItems(self.data_manager.get_classes())
        controls.addWidget(self.class_list)
        
        controls.addStretch()
        layout.addLayout(controls, stretch=1)
        self.setLayout(layout)

    def add_class(self):
        name = self.class_input.text()
        if name:
            self.data_manager.add_class(name)
            self.class_list.clear()
            self.class_list.addItems(self.data_manager.get_classes())
            self.class_input.clear()

    def start_camera(self):
        if not self.is_running:
            self.camera = Camera().start()
            self.timer.start(30)
            self.is_running = True
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)

    def stop_camera(self):
        if self.is_running:
            self.timer.stop()
            if self.camera:
                self.camera.stop()
            self.is_running = False
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.video_label.setPixmap(QPixmap())
            self.video_label.setText("Camera Feed")

    def update_frame(self):
        if self.camera:
            frame = self.camera.get_frame()
            if frame is not None:
                frame = cv2.resize(frame, (640, 480))
                # Face detection disabled for performance
                # locations, names, _ = self.face_handler.process_frame(frame)
                # frame = draw_faces_on_frame(frame, locations, names)
                self.video_label.setPixmap(convert_cv_qt(frame))


# ==================== INCIDENT DETECTION WORKER ====================
class IncidentDetectionWorker(QThread):
    """Background worker for incident detection."""
    status_update = Signal(str)
    moments_found = Signal(list)
    error = Signal(str)
    finished = Signal()
    
    def __init__(self, api_key: str, incident_type: IncidentType, 
                 custom_query: str, sensitivity: str):
        super().__init__()
        self.api_key = api_key
        self.incident_type = incident_type
        self.custom_query = custom_query
        self.sensitivity = sensitivity
    
    def run(self):
        try:
            from twelvelabs_client import TwelveLabsClient
            
            self.status_update.emit("Initializing...")
            client = TwelveLabsClient(api_key=self.api_key)
            
            workflow = IncidentWorkflow(sensitivity=self.sensitivity)
            queries = workflow.get_queries(self.incident_type, self.custom_query)
            
            self.status_update.emit(f"Searching with {len(queries)} queries...")
            
            top_k = {"Low": 2, "Medium": 3, "High": 5}.get(self.sensitivity, 3)
            all_moments = client.search_multiple_queries(queries, top_k_per_query=top_k)
            
            self.status_update.emit(f"Found {len(all_moments)} raw moments. Merging...")
            
            evidence_clips = workflow.merge_moments(all_moments)
            
            self.status_update.emit(f"Processed into {len(evidence_clips)} evidence clips")
            self.moments_found.emit(evidence_clips)
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))


class CustomSearchWorker(QThread):
    """Background worker for custom query search."""
    status_update = Signal(str)
    moments_found = Signal(list)
    error = Signal(str)
    finished = Signal()
    
    def __init__(self, api_key: str, query: str):
        super().__init__()
        self.api_key = api_key
        self.query = query
    
    def run(self):
        try:
            from twelvelabs_client import TwelveLabsClient
            
            self.status_update.emit(f"Analyzing: {self.query[:40]}...")
            client = TwelveLabsClient(api_key=self.api_key)
            
            # Use search_moments with the single custom query
            moments = client.search_moments(self.query, top_k=10)
            
            self.status_update.emit(f"Found {len(moments)} moments")
            
            # Convert to EvidenceClip objects
            workflow = IncidentWorkflow()
            evidence_clips = workflow.merge_moments(moments)
            
            self.status_update.emit(f"Processed into {len(evidence_clips)} evidence clips")
            self.moments_found.emit(evidence_clips)
            self.finished.emit()
            
        except Exception as e:
            self.error.emit(str(e))


# ==================== VIDEO ANALYSIS TAB ====================
class VideoAnalysisTab(QWidget):
    """Video Analysis tab with Incident Builder workflow."""
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.indexed_asset_id = None
        self.evidence_clips = []
        self.current_report = None
        self.worker = None
        self.upload_worker = None
        self.video_duration = 0
        
        # Playback state
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_video)
        self.is_playing = False
        self.fps = 30.0
        self.was_playing = False
        
        self.init_ui()
    
    def init_ui(self):
        main_layout = QHBoxLayout()
        
        # LEFT PANEL: Video + Controls
        left_panel = QVBoxLayout()
        
        # File controls
        file_row = QHBoxLayout()
        self.btn_open = QPushButton(" Open Video")
        self.btn_open.setIcon(qta.icon('fa5s.folder-open'))
        self.btn_open.clicked.connect(self.open_file)
        file_row.addWidget(self.btn_open)
        
        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: gray;")
        file_row.addWidget(self.file_label, stretch=1)
        
        self.btn_upload = QPushButton("Index with Twelvelabs")
        self.btn_upload.setIcon(qta.icon('fa5s.database'))
        self.btn_upload.clicked.connect(self.upload_video)
        self.btn_upload.setEnabled(False)
        file_row.addWidget(self.btn_upload)
        
        left_panel.addLayout(file_row)
        
        # Video player placeholder
        self.video_label = QLabel("Video Preview")
        self.video_label.setMinimumSize(480, 360)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: #1a1a1a; border: 1px solid #444;")
        left_panel.addWidget(self.video_label)
        
        # Playback controls
        controls_row = QHBoxLayout()
        
        self.btn_play = QPushButton("▶ Play")
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setEnabled(False)
        controls_row.addWidget(self.btn_play)
        
        # Playback slider
        self.time_label = QLabel("00:00")
        controls_row.addWidget(self.time_label)
        
        self.playback_slider = QSlider(Qt.Horizontal)
        self.playback_slider.setEnabled(False)
        self.playback_slider.sliderPressed.connect(self.slider_pressed)
        self.playback_slider.sliderReleased.connect(self.slider_released)
        self.playback_slider.valueChanged.connect(self.slider_moved)
        controls_row.addWidget(self.playback_slider, stretch=1)
        
        self.duration_label = QLabel("00:00")
        controls_row.addWidget(self.duration_label)
        
        left_panel.addLayout(controls_row)
        
        # Status
        self.status_label = QLabel("Select a video file to begin")
        self.status_label.setStyleSheet("color: #888; padding: 5px;")
        left_panel.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        left_panel.addWidget(self.progress_bar)
        
        main_layout.addLayout(left_panel, stretch=3)
        
        # RIGHT PANEL: Incident Builder
        right_panel = QVBoxLayout()
        
        # Incident Builder Group
        incident_group = QGroupBox("Incident Builder")
        # Use QFormLayout for clean alignment and spacing
        incident_layout = QFormLayout()
        incident_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        incident_layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        incident_layout.setSpacing(10) # Nice gap between rows
        
        # Incident Type
        self.incident_combo = QComboBox()
        for itype in IncidentType:
            self.incident_combo.addItem(itype.value, itype)
        incident_layout.addRow("Incident Type:", self.incident_combo)
        
        # Location
        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("e.g. Building A - Entrance")
        incident_layout.addRow("Location:", self.location_input)
        
        # Camera ID
        self.camera_id_input = QLineEdit()
        self.camera_id_input.setPlaceholderText("e.g. CAM-01")
        incident_layout.addRow("Camera ID:", self.camera_id_input)
        
        # Sensitivity
        self.sensitivity_combo = QComboBox()
        self.sensitivity_combo.addItems(["Low", "Medium", "High"])
        self.sensitivity_combo.setCurrentText("Medium")
        incident_layout.addRow("Sensitivity:", self.sensitivity_combo)
        
        # Custom Query
        self.custom_query_input = QLineEdit()
        self.custom_query_input.setPlaceholderText("Enter any search prompt...")
        incident_layout.addRow("Custom Query:", self.custom_query_input)
        
        # Buttons row
        btn_row = QHBoxLayout()
        
        # Detect Button (uses incident type + custom query)
        self.btn_detect = QPushButton("Detect Incidents")
        self.btn_detect.setIcon(qta.icon('fa5s.search-plus', color='white', color_disabled='white'))
        self.btn_detect.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        self.btn_detect.clicked.connect(self.detect_incidents)
        self.btn_detect.setEnabled(False)
        btn_row.addWidget(self.btn_detect)
        
        # Custom Search Button (uses only custom query)
        self.btn_custom_search = QPushButton("Custom Search")
        self.btn_custom_search.setIcon(qta.icon('fa5s.search', color='white', color_disabled='white'))
        self.btn_custom_search.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold; padding: 10px;")
        self.btn_custom_search.clicked.connect(self.custom_search)
        self.btn_custom_search.setEnabled(False)
        btn_row.addWidget(self.btn_custom_search)
        
        incident_layout.addRow(btn_row)
        
        incident_group.setLayout(incident_layout)
        right_panel.addWidget(incident_group)
        
        # Evidence Table
        evidence_group = QGroupBox("Evidence Clips")
        evidence_layout = QVBoxLayout()
        
        self.evidence_table = QTableWidget()
        self.evidence_table.setColumnCount(6)
        # Using simple header text, icons could be added to items if needed
        self.evidence_table.setHorizontalHeaderLabels(["Sel", "Start", "End", "Conf", "Label", "Notes"])
        self.evidence_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.evidence_table.setSelectionBehavior(QTableWidget.SelectRows)
        evidence_layout.addWidget(self.evidence_table)
        
        # Jump button
        btn_row = QHBoxLayout()
        self.btn_jump = QPushButton("Jump to Selected")
        self.btn_jump.setIcon(qta.icon('fa5s.forward'))
        self.btn_jump.clicked.connect(self.jump_to_selected)
        btn_row.addWidget(self.btn_jump)
        btn_row.addStretch()
        evidence_layout.addLayout(btn_row)
        
        evidence_group.setLayout(evidence_layout)
        right_panel.addWidget(evidence_group)
        
        # Report Actions
        actions_group = QGroupBox("Report Actions")
        actions_layout = QHBoxLayout()
        
        self.btn_generate = QPushButton("Generate Report")
        self.btn_generate.setIcon(qta.icon('fa5s.file-alt', color='white', color_disabled='white'))
        self.btn_generate.clicked.connect(self.generate_report)
        self.btn_generate.setEnabled(False)
        actions_layout.addWidget(self.btn_generate)
        
        self.btn_export_json = QPushButton("Export JSON")
        self.btn_export_json.setIcon(qta.icon('fa5s.save', color='white', color_disabled='white'))
        self.btn_export_json.clicked.connect(self.export_json)
        self.btn_export_json.setEnabled(False)
        actions_layout.addWidget(self.btn_export_json)
        
        self.btn_export_pdf = QPushButton("Export PDF")
        self.btn_export_pdf.setIcon(qta.icon('fa5s.file-pdf', color='white', color_disabled='white'))
        self.btn_export_pdf.setStyleSheet("background-color: #D32F2F; color: white;")
        self.btn_export_pdf.clicked.connect(self.export_pdf)
        self.btn_export_pdf.setEnabled(False)
        actions_layout.addWidget(self.btn_export_pdf)
        
        actions_group.setLayout(actions_layout)
        right_panel.addWidget(actions_group)
        
        # Report View
        report_group = QGroupBox("Incident Report")
        report_layout = QVBoxLayout()
        
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)
        report_layout.addWidget(self.report_text)
        
        report_group.setLayout(report_layout)
        right_panel.addWidget(report_group, stretch=1)
        
        main_layout.addLayout(right_panel, stretch=1)
        self.setLayout(main_layout)

    # ---- Playback Logic ----
    def toggle_playback(self):
        if self.is_playing:
            self.timer.stop()
            self.is_playing = False
            self.btn_play.setText("▶ Play")
        else:
            self.timer.start(33)  # ~30 FPS
            self.is_playing = True
            self.btn_play.setText("⏸ Pause")

    def update_video(self):
        if not self.cap or not self.cap.isOpened():
            return
            
        ret, frame = self.cap.read()
        if ret:
            # Update slider without triggering seek
            self.playback_slider.blockSignals(True)
            current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.playback_slider.setValue(current_frame)
            self.playback_slider.blockSignals(False)
            
            # Update time label
            seconds = current_frame / self.fps
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            self.time_label.setText(f"{mins:02d}:{secs:02d}")
            
            # Draw frame
            frame = cv2.resize(frame, (480, 360))
            self.video_label.setPixmap(convert_cv_qt(frame))
        else:
            # End of video
            self.toggle_playback()
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def slider_pressed(self):
        self.was_playing = self.is_playing
        if self.is_playing:
            self.toggle_playback()

    def slider_released(self):
        target_frame = self.playback_slider.value()
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (480, 360))
                self.video_label.setPixmap(convert_cv_qt(frame))
        
        if self.was_playing:
            self.toggle_playback()

    def slider_moved(self, value):
        # Only seek if user is dragging (timer updates are blocked)
        if self.cap:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, value)
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.resize(frame, (480, 360))
                self.video_label.setPixmap(convert_cv_qt(frame))
                
                seconds = value / self.fps
                mins = int(seconds // 60)
                secs = int(seconds % 60)
                self.time_label.setText(f"{mins:02d}:{secs:02d}")

    # ---- File Operations ----
    def open_file(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilters(["Video files (*.mp4 *.avi *.mkv *.mov *.webm)"])
        if file_dialog.exec():
            files = file_dialog.selectedFiles()
            if files:
                self.current_file = files[0]
                self.file_label.setText(os.path.basename(self.current_file))
                self.file_label.setStyleSheet("color: white;")
                self.btn_upload.setEnabled(True)
                self.btn_play.setEnabled(True)
                self.playback_slider.setEnabled(True)
                self.status_label.setText("Video loaded. Click 'Index with Twelvelabs' to start.")
                
                # Initialize video capture
                if self.cap:
                    self.cap.release()
                self.cap = cv2.VideoCapture(self.current_file)
                
                self.fps = self.cap.get(cv2.CAP_PROP_FPS)
                frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
                
                if self.fps > 0:
                    self.video_duration = frame_count / self.fps
                    mins = int(self.video_duration // 60)
                    secs = int(self.video_duration % 60)
                    self.duration_label.setText(f"{mins:02d}:{secs:02d}")
                    
                    self.playback_slider.setRange(0, int(frame_count))
                
                # Show first frame
                ret, frame = self.cap.read()
                if ret:
                    frame = cv2.resize(frame, (480, 360))
                    self.video_label.setPixmap(convert_cv_qt(frame))

    
    def upload_video(self):
        if not self.current_file:
            return
        
        self.btn_upload.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText("Uploading to Twelve Labs...")
        
        # Use a simple upload in background
        self.upload_worker = UploadWorker(self.current_file, TWELVE_LABS_API_KEY)
        self.upload_worker.status_update.connect(self.on_status_update)
        self.upload_worker.upload_complete.connect(self.on_upload_complete)
        self.upload_worker.error.connect(self.on_error)
        self.upload_worker.start()
    
    def on_upload_complete(self, asset_id: str):
        self.indexed_asset_id = asset_id
        self.progress_bar.hide()
        self.status_label.setText(f"Video indexed! Asset ID: {asset_id[:20]}...")
        self.btn_detect.setEnabled(True)
        self.btn_custom_search.setEnabled(True)
        self.btn_upload.setText("Video Indexed")
        self.btn_upload.setIcon(qta.icon('fa5s.check'))
    
    def on_status_update(self, status: str):
        self.status_label.setText(status)
    
    def on_error(self, error: str):
        self.progress_bar.hide()
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("color: red;")
        self.btn_upload.setEnabled(True)
    
    # ---- Incident Detection ----
    def detect_incidents(self):
        if not self.indexed_asset_id:
            self.status_label.setText("Please upload a video first")
            return
        
        incident_type = self.incident_combo.currentData()
        sensitivity = self.sensitivity_combo.currentText()
        custom_query = self.custom_query_input.text()
        
        self.btn_detect.setEnabled(False)
        self.progress_bar.show()
        
        self.worker = IncidentDetectionWorker(
            TWELVE_LABS_API_KEY, incident_type, custom_query, sensitivity
        )
        self.worker.status_update.connect(self.on_status_update)
        self.worker.moments_found.connect(self.on_moments_found)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_detection_finished)
        self.worker.start()
    
    def on_moments_found(self, clips: list):
        self.evidence_clips = clips
        self.populate_evidence_table()
    
    def on_detection_finished(self):
        self.progress_bar.hide()
        self.btn_detect.setEnabled(True)
        self.btn_custom_search.setEnabled(True)
        self.btn_generate.setEnabled(len(self.evidence_clips) > 0)
    
    def custom_search(self):
        """Run a custom search using only the custom query input."""
        if not self.indexed_asset_id:
            self.status_label.setText("Please upload a video first")
            return
        
        custom_query = self.custom_query_input.text().strip()
        if not custom_query:
            self.status_label.setText("Please enter a custom query")
            return
        
        self.btn_detect.setEnabled(False)
        self.btn_custom_search.setEnabled(False)
        self.progress_bar.show()
        self.status_label.setText(f"Searching: {custom_query[:50]}...")
        
        # Use a simple worker to run the search
        self.custom_worker = CustomSearchWorker(TWELVE_LABS_API_KEY, custom_query)
        self.custom_worker.status_update.connect(self.on_status_update)
        self.custom_worker.moments_found.connect(self.on_moments_found)
        self.custom_worker.error.connect(self.on_error)
        self.custom_worker.finished.connect(self.on_detection_finished)
        self.custom_worker.start()
    
    def populate_evidence_table(self):
        self.evidence_table.setRowCount(len(self.evidence_clips))
        
        for i, clip in enumerate(self.evidence_clips):
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(clip.included)
            checkbox.stateChanged.connect(lambda state, idx=i: self.toggle_include(idx, state))
            self.evidence_table.setCellWidget(i, 0, checkbox)
            
            # Times
            self.evidence_table.setItem(i, 1, QTableWidgetItem(clip.start_formatted))
            self.evidence_table.setItem(i, 2, QTableWidgetItem(clip.end_formatted))
            
            # Confidence
            conf_item = QTableWidgetItem(f"{clip.confidence:.0%}")
            self.evidence_table.setItem(i, 3, conf_item)
            
            # Label
            self.evidence_table.setItem(i, 4, QTableWidgetItem(clip.label))
            
            # Notes (editable)
            notes_item = QTableWidgetItem(clip.notes)
            notes_item.setFlags(notes_item.flags() | Qt.ItemIsEditable)
            self.evidence_table.setItem(i, 5, notes_item)
        
        self.evidence_table.resizeColumnsToContents()
    
    def toggle_include(self, idx: int, state: int):
        if idx < len(self.evidence_clips):
            self.evidence_clips[idx].included = (state == Qt.Checked)
    
    def jump_to_selected(self):
        row = self.evidence_table.currentRow()
        if 0 <= row < len(self.evidence_clips):
            clip = self.evidence_clips[row]
            self.jump_to_time(clip.start_time)
    
    def jump_to_time(self, seconds: float):
        """Jump video preview to specified time"""
        if not self.current_file:
            return
        
        cap = cv2.VideoCapture(self.current_file)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps > 0:
            frame_num = int(seconds * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = cap.read()
            if ret:
                frame = cv2.resize(frame, (480, 360))
                self.video_label.setPixmap(convert_cv_qt(frame))
                
                mins = int(seconds // 60)
                secs = int(seconds % 60)
                self.time_label.setText(f"{mins:02d}:{secs:02d}")
        cap.release()
    
    # ---- Report Generation ----
    def generate_report(self):
        # Update notes from table
        for i, clip in enumerate(self.evidence_clips):
            notes_item = self.evidence_table.item(i, 5)
            if notes_item:
                clip.notes = notes_item.text()
        
        incident_type = self.incident_combo.currentData()
        location = self.location_input.text()
        camera_id = self.camera_id_input.text()
        
        workflow = IncidentWorkflow()
        self.current_report = workflow.generate_report(
            incident_type=incident_type,
            evidence=self.evidence_clips,
            location=location,
            camera_id=camera_id
        )
        
        # Display report
        self.display_report()
        self.btn_export_json.setEnabled(True)
        self.btn_export_pdf.setEnabled(True)
    
    def display_report(self):
        if not self.current_report:
            return
        
        r = self.current_report
        
        text = f"""
╔══════════════════════════════════════════════════════════════╗
║  SECURITY INCIDENT REPORT
╚══════════════════════════════════════════════════════════════╝

📋 INCIDENT TYPE: {r.incident_type}
📍 LOCATION: {r.location}
📷 CAMERA: {r.camera_id}
🕐 TIME RANGE: {r.time_range}
📅 GENERATED: {r.created_at[:19]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 EXECUTIVE SUMMARY
"""
        for bullet in r.executive_summary:
            text += f"  • {bullet}\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "\n⏱️ TIMELINE\n"
        
        for event in r.timeline:
            text += f"  [{event['time']}] {event['event']}"
            if event.get('notes'):
                text += f" — {event['notes']}"
            text += "\n"
        
        text += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "\n🔧 RECOMMENDED ACTIONS\n"
        
        for action in r.recommended_actions:
            text += f"  → {action}\n"
        
        self.report_text.setText(text)
    
    def export_json(self):
        if not self.current_report:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Report", 
            f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if filename:
            with open(filename, 'w') as f:
                f.write(self.current_report.to_json())
            
            QMessageBox.information(self, "Export Complete", f"Report saved to:\n{filename}")
    
    def export_pdf(self):
        if not self.current_report:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export PDF Report", 
            f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            "PDF Files (*.pdf)"
        )
        
        if filename:
            try:
                from pdf_report import generate_pdf_report
                generate_pdf_report(self.current_report, filename)
                QMessageBox.information(self, "Export Complete", f"PDF saved to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to generate PDF:\n{str(e)}")


# ==================== UPLOAD WORKER ====================
class UploadWorker(QThread):
    """Background worker for video upload."""
    status_update = Signal(str)
    upload_complete = Signal(str)
    error = Signal(str)
    
    def __init__(self, file_path: str, api_key: str):
        super().__init__()
        self.file_path = file_path
        self.api_key = api_key
    
    def run(self):
        try:
            from twelvelabs_client import TwelveLabsClient
            
            client = TwelveLabsClient(api_key=self.api_key)
            
            asset_id = client.upload_and_index_video(
                self.file_path,
                callback=lambda s: self.status_update.emit(s)
            )
            
            self.upload_complete.emit(asset_id)
            
        except Exception as e:
            self.error.emit(str(e))


# ==================== GRID TAB ====================
class GridTab(QWidget):
    """CCTV Grid with AI-Powered Real-Time Monitoring."""
    
    def __init__(self, multi_cam):
        super().__init__()
        self.multi_cam = multi_cam
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_grid)
        self.timer.start(100)
        self.grid_widgets = {}
        
        # RTStream state
        self.rtstream_monitor = None
        self.current_stream_id = None
        self.current_index_id = None
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()
        
        # LEFT PANEL: Controls
        controls = QVBoxLayout()
        
        # Camera Section
        controls.addWidget(QLabel("<b>📹 CCTV Controls</b>"))
        
        self.cam_input = QLineEdit()
        self.cam_input.setPlaceholderText("RTSP URL or camera ID")
        controls.addWidget(self.cam_input)
        
        cam_btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Camera")
        self.btn_add.clicked.connect(self.add_camera)
        cam_btn_row.addWidget(self.btn_add)
        
        self.btn_add_webcam = QPushButton("📷 Webcam")
        self.btn_add_webcam.setStyleSheet("background-color: #4CAF50;")
        self.btn_add_webcam.clicked.connect(self.add_webcam)
        cam_btn_row.addWidget(self.btn_add_webcam)
        
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self.remove_camera)
        cam_btn_row.addWidget(self.btn_remove)
        controls.addLayout(cam_btn_row)
        
        self.cam_list = QListWidget()
        self.cam_list.setMaximumHeight(100)
        controls.addWidget(self.cam_list)
        
        # AI Monitoring Section
        controls.addWidget(QLabel(""))  # Spacer
        controls.addWidget(QLabel("<b>🤖 AI Monitoring (VideoDB)</b>"))
        
        # Scenario dropdown
        self.scenario_combo = QComboBox()
        from rtstream_monitor import DetectionScenario, get_scenario_prompt
        for scenario in DetectionScenario:
            self.scenario_combo.addItem(scenario.value, scenario)
        self.scenario_combo.currentIndexChanged.connect(self.on_scenario_changed)
        controls.addWidget(self.scenario_combo)
        
        # Custom prompt
        controls.addWidget(QLabel("Detection Prompt:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(80)
        self.prompt_edit.setPlaceholderText("AI will monitor for this...")
        # Set initial prompt
        self.on_scenario_changed(0)
        controls.addWidget(self.prompt_edit)
        
        # Stream source for monitoring (VideoDB needs RTSP)
        controls.addWidget(QLabel("Stream Source:"))
        self.stream_combo = QComboBox()
        self.stream_combo.setEditable(True)
        self.stream_combo.addItems([
            "rtsp://samples.rts.videodb.io:8554/floods",
            "Webcam (local only)",
            "Custom RTSP URL..."
        ])
        controls.addWidget(self.stream_combo)
        
        # Note about VideoDB
        note = QLabel("⚠️ AI monitoring requires RTSP stream")
        note.setStyleSheet("color: #888; font-size: 10px;")
        controls.addWidget(note)
        
        # Webhook URL (optional)
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("Webhook URL for alerts (optional)")
        controls.addWidget(self.webhook_input)
        
        # Control buttons
        monitor_btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("🔗 Connect Stream")
        self.btn_connect.clicked.connect(self.connect_stream)
        monitor_btn_row.addWidget(self.btn_connect)
        
        self.btn_start_monitor = QPushButton("▶ Start Monitoring")
        self.btn_start_monitor.clicked.connect(self.start_monitoring)
        self.btn_start_monitor.setEnabled(False)
        monitor_btn_row.addWidget(self.btn_start_monitor)
        controls.addLayout(monitor_btn_row)
        
        self.btn_stop_monitor = QPushButton("⏹ Stop Monitoring")
        self.btn_stop_monitor.clicked.connect(self.stop_monitoring)
        self.btn_stop_monitor.setEnabled(False)
        controls.addWidget(self.btn_stop_monitor)
        
        # Status
        self.monitor_status = QLabel("Not connected")
        self.monitor_status.setStyleSheet("color: #888;")
        controls.addWidget(self.monitor_status)
        
        controls.addStretch()
        main_layout.addLayout(controls, stretch=1)
        
        # RIGHT PANEL: Grid + Event Log
        right_panel = QVBoxLayout()
        
        # Camera Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_container.setLayout(self.grid_layout)
        scroll.setWidget(self.grid_container)
        right_panel.addWidget(scroll, stretch=2)
        
        # Event Log
        right_panel.addWidget(QLabel("<b>📋 Detected Events</b>"))
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumHeight(150)
        self.event_log.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #4CAF50;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        right_panel.addWidget(self.event_log)
        
        # Refresh events button
        self.btn_refresh_events = QPushButton("🔄 Refresh Events")
        self.btn_refresh_events.clicked.connect(self.refresh_events)
        self.btn_refresh_events.setEnabled(False)
        right_panel.addWidget(self.btn_refresh_events)
        
        main_layout.addLayout(right_panel, stretch=3)
        self.setLayout(main_layout)
    
    def on_scenario_changed(self, index):
        """Update prompt when scenario changes."""
        from rtstream_monitor import get_scenario_prompt
        scenario = self.scenario_combo.currentData()
        if scenario:
            self.prompt_edit.setText(get_scenario_prompt(scenario))
    
    def connect_stream(self):
        """Connect to RTSP stream via VideoDB."""
        rtsp_url = self.stream_combo.currentText().strip()
        
        # Handle special cases
        if "Webcam" in rtsp_url or rtsp_url == "Webcam (local only)":
            self.monitor_status.setText("⚠️ Webcam requires RTSP - use CCTV Grid")
            return
        if "Custom" in rtsp_url or not rtsp_url:
            self.monitor_status.setText("⚠️ Enter a valid RTSP URL")
            return
        
        self.monitor_status.setText("Connecting...")
        
        try:
            from rtstream_monitor import RTStreamMonitor, StreamConfig, DetectionScenario
            
            # Initialize monitor if needed
            if not self.rtstream_monitor:
                self.rtstream_monitor = RTStreamMonitor(
                    api_key="sk-idjvWUi2BhlxJnCKaHFUIaKmrdFLWteLPb2OqHmNjzY"
                )
            
            scenario = self.scenario_combo.currentData() or DetectionScenario.CUSTOM
            config = StreamConfig(
                name=f"{scenario.value} Monitor",
                rtsp_url=rtsp_url,
                scenario=scenario,
                custom_prompt=self.prompt_edit.toPlainText()
            )
            
            self.current_stream_id = self.rtstream_monitor.connect_stream(config)
            self.monitor_status.setText(f"✅ Connected: {self.current_stream_id[:20]}...")
            self.btn_start_monitor.setEnabled(True)
            self.btn_connect.setEnabled(False)
            
        except Exception as e:
            self.monitor_status.setText(f"❌ Error: {str(e)[:50]}")
    
    def start_monitoring(self):
        """Start AI monitoring on the connected stream."""
        if not self.current_stream_id:
            return
        
# ==================== LOCAL AI WORKER (YOLO-powered) ====================
class DeepAnalyzeWorker(QThread):
    """Worker thread for capturing and analyzing video without freezing UI."""
    status_update = Signal(str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    def run(self):
        import cv2
        import tempfile
        import os
        import time
        from twelvelabs_client import TwelveLabsClient

        try:
            # 1. Capture Video (Webcam)
            self.status_update.emit("Capturing 5s clip...")
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                raise Exception("Could not open webcam")
            
            # Use lower res for faster upload/analysis
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            
            # Temp file
            fd, temp_path = tempfile.mkstemp(suffix='.mp4')
            os.close(fd)
            
            writer = cv2.VideoWriter(
                temp_path, 
                cv2.VideoWriter_fourcc(*'mp4v'), 
                fps, 
                (640, 480)
            )
            
            # Record 5 seconds
            start_time = time.time()
            while (time.time() - start_time) < 5.0:
                ret, frame = cap.read()
                if ret:
                    writer.write(frame)
            
            writer.release()
            cap.release()
            
            # 2. Upload & Analyze
            self.status_update.emit("Uploading to Twelve Labs...")
            client = TwelveLabsClient(self.api_key)
            
            # Use the exact prompt for "describe"
            self.status_update.emit("AI Analysis in progress...")
            analysis = client.analyze_video(temp_path, "Describe the situation, potential threats, and activities in detail.")
            
            # Cleanup
            try:
                os.remove(temp_path)
            except:
                pass
                
            self.finished.emit(f"AI Analysis: {analysis}")

        except Exception as e:
            self.error.emit(str(e))



class ClickableCameraWidget(QLabel):
    """Custom Label that emits clicked signal."""
    clicked = Signal(str)  # Emits cam_id

    def __init__(self, cam_id, text="", parent=None):
        super().__init__(text, parent)
        self.cam_id = cam_id
        self.selected = False
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.default_style = "background-color: #1a1a1a; border: 2px solid #333;"
        self.selected_style = "background-color: #1a1a1a; border: 3px solid #00E676;" # High-vis green
        self.setStyleSheet(self.default_style)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.cam_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        self.selected = selected
        self.setStyleSheet(self.selected_style if selected else self.default_style)


class LocalAIWorker(QThread):
    """Uses YOLO detections for real-time object-based rule matching + behavior detection."""
    event_detected = Signal(dict)
    
    def __init__(self, multi_cam, rules):
        super().__init__()
        self.multi_cam = multi_cam
        self.rules = rules  # List of {id, scenario, prompt, enabled}
        self.running = True
        self.last_detections = set()  # Track to avoid duplicate alerts
        self.tracker = None  # Person tracker
        self.vehicle_tracker = None  # Vehicle tracker
        self.crowd_alerted = False  # One-shot crowd alert
        
    def run(self):
        import time
        
        # Initialize trackers
        from person_tracker import PersonTracker, VehicleTracker
        self.tracker = PersonTracker(
            loiter_time=15.0,    # 15 seconds for demo
            loiter_radius=100.0  # pixels movement threshold
        )
        self.vehicle_tracker = VehicleTracker(
            loiter_time=20.0,    # 20 seconds for vehicles
            loiter_radius=50.0   # Vehicles move less
        )
        
        while self.running:
            time.sleep(0.5)  # Check twice per second for tracking accuracy
            
            if not self.running:
                break
            
            # Get detections from camera
            detections = []
            if hasattr(self.multi_cam, 'cameras'):
                for cid, cam in self.multi_cam.cameras.items():
                    if cam.get('detections'):
                        detections = cam['detections']
                        break
            
            # Update trackers
            tracked_persons = self.tracker.update(detections)
            tracked_vehicles = self.vehicle_tracker.update(detections)
            
            # Count persons for crowd detection
            person_count = len([d for d in detections if d['class'] == 'person'])
            
            # ========== PERSON LOITERING ==========
            for person in tracked_persons:
                if person['is_loitering'] and not person['loitering_alerted']:
                    for rule in self.rules:
                        prompt = rule['prompt'].lower()
                        if 'loiter' in prompt or 'stay' in prompt or 'remain' in prompt or 'linger' in prompt:
                            if 'vehicle' not in prompt and 'car' not in prompt:
                                msg = f"⚠️ [{rule['scenario']}] LOITERING: Person #{person['id']} in same area for {person['time_tracked']:.0f}s"
                                self._emit_event(msg, rule['id'], "loitering_person")
                                break
            
            # ========== VEHICLE LOITERING ==========
            for vehicle in tracked_vehicles:
                if vehicle['is_loitering'] and not vehicle['loitering_alerted']:
                    for rule in self.rules:
                        prompt = rule['prompt'].lower()
                        if ('vehicle' in prompt or 'car' in prompt or 'parked' in prompt) and ('loiter' in prompt or 'stay' in prompt or 'parked' in prompt):
                            msg = f"🚗 [{rule['scenario']}] PARKED VEHICLE: Vehicle #{vehicle['id']} stationary for {vehicle['time_tracked']:.0f}s"
                            self._emit_event(msg, rule['id'], "loitering_vehicle")
                            break
            
            # ========== CROWD DETECTION ==========
            for rule in self.rules:
                prompt = rule['prompt'].lower()
                if 'crowd' in prompt or 'gathering' in prompt or 'group' in prompt:
                    # Extract threshold from prompt or default to 3
                    threshold = 3
                    if person_count >= threshold and not self.crowd_alerted:
                        msg = f"👥 [{rule['scenario']}] CROWD ALERT: {person_count} people detected"
                        self._emit_event(msg, rule['id'], "crowd")
                        self.crowd_alerted = True
                    elif person_count < threshold:
                        self.crowd_alerted = False  # Reset for next alert
            
            # ========== ZONE INTRUSION DETECTION ==========
            try:
                from zone_manager import get_zone_manager
                zone_mgr = get_zone_manager()
                intrusions = zone_mgr.check_intrusions(detections)
                for intrusion in intrusions:
                    zone_name = intrusion['zone']
                    msg = f"🚧 ZONE INTRUSION: Person entered '{zone_name}'"
                    # Find a matching rule or use first rule
                    for rule in self.rules:
                        prompt = rule['prompt'].lower()
                        if 'zone' in prompt or 'intrusion' in prompt or 'restricted' in prompt:
                            msg = f"🚧 [{rule['scenario']}] ZONE INTRUSION: '{zone_name}'"
                            self._emit_event(msg, rule['id'], "zone_intrusion")
                            break
                    else:
                        # No matching rule, still emit with generic ID
                        if self.rules:
                            self._emit_event(msg, self.rules[0]['id'], "zone_intrusion")
            except Exception as e:
                pass  # Zone detection is optional
            
            # Get set of detected class names
            detected_classes = set(d['class'] for d in detections)
            
            # Check each rule against detections
            for rule in self.rules:
                if not rule.get('enabled', True):
                    continue
                    
                prompt = rule['prompt'].lower()
                scenario = rule['scenario']
                
                # Skip behavior rules (handled separately above)
                if 'loiter' in prompt or 'stay' in prompt or 'remain' in prompt or 'crowd' in prompt or 'gathering' in prompt:
                    continue
                
                # Check if any detected class matches the prompt
                for det in detections:
                    class_name = det['class']
                    conf = det['confidence']
                    
                    # Match if class name appears in prompt
                    if class_name in prompt or self._fuzzy_match(prompt, class_name):
                        # Avoid spamming same detection
                        key = f"{rule['id']}_{class_name}"
                        if key not in self.last_detections:
                            self.last_detections.add(key)
                            
                            msg = f"🎯 [{scenario}] DETECTED: {class_name} (conf: {conf:.2f})"
                            event_data = {
                                "description": msg,
                                "timestamp": datetime.now().strftime("%H:%M:%S"),
                                "rule_id": rule['id'],
                                "class": class_name,
                                "confidence": conf
                            }
                            self.event_detected.emit(event_data)
            
            # Clear old detections periodically (allow re-detection)
            if len(self.last_detections) > 50:
                self.last_detections.clear()
    
    def _fuzzy_match(self, prompt: str, class_name: str) -> bool:
        """Check for related terms."""
        synonyms = {
            'phone': ['cell phone', 'mobile', 'smartphone'],
            'human': ['person', 'people', 'man', 'woman'],
            'vehicle': ['car', 'truck', 'bus', 'motorcycle'],
            'weapon': ['knife', 'scissors'],
            'intruder': ['person'],
            'suspicious': ['person'],  # Map suspicious to person detection
        }
        
        for key, values in synonyms.items():
            if key in prompt:
                if class_name in values or class_name == key:
                    return True
        return False
    
    def _emit_event(self, msg: str, rule_id: int, event_type: str):
        """Helper to emit event data and trigger desktop notification."""
        event_data = {
            "description": msg,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "rule_id": rule_id,
            "event_type": event_type
        }
        self.event_detected.emit(event_data)
        
        # Trigger desktop notification
        try:
            from notifications import notify
            # Extract key info for notification
            if "loitering" in event_type.lower():
                notify("⚠️ Security Alert", msg[:100])
            elif "crowd" in event_type.lower():
                notify("👥 Crowd Alert", msg[:100])
            elif "vehicle" in event_type.lower():
                notify("🚗 Vehicle Alert", msg[:100])
            else:
                notify("🎯 Detection", msg[:100])
        except Exception as e:
            pass  # Notifications are optional


# ==================== GRID TAB ====================
class GridTab(QWidget):
    """CCTV Grid with AI-Powered Real-Time Monitoring."""
    
    def __init__(self, multi_cam):
        super().__init__()
        self.multi_cam = multi_cam
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_grid)
        self.timer.start(100)
        self.grid_widgets = {}
        
        # RTStream state
        self.rtstream_monitor = None
        self.current_stream_id = None
        self.current_index_id = None
        self.local_worker = None  # For demo mode
        
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()
        # ... (rest of UI code remains same until connect_stream) ...
        # LEFT PANEL: Controls
        controls = QVBoxLayout()
        
        # Camera Section
        controls.addWidget(QLabel("<b>CCTV Controls</b>"))
        
        self.cam_input = QLineEdit()
        self.cam_input.setPlaceholderText("RTSP URL or camera ID")
        controls.addWidget(self.cam_input)
        
        cam_btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Camera")
        self.btn_add.clicked.connect(self.add_camera)
        cam_btn_row.addWidget(self.btn_add)
        
        self.btn_add_webcam = QPushButton("Webcam")
        self.btn_add_webcam.setIcon(qta.icon('fa5s.camera'))
        self.btn_add_webcam.setStyleSheet("background-color: #4CAF50;")
        self.btn_add_webcam.clicked.connect(self.add_webcam)
        cam_btn_row.addWidget(self.btn_add_webcam)
        
        self.btn_add_dummy = QPushButton("Add Demo Cam")
        self.btn_add_dummy.setIcon(qta.icon('fa5s.plus-circle'))
        self.btn_add_dummy.clicked.connect(self.add_dummy_camera)
        cam_btn_row.addWidget(self.btn_add_dummy)
        
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.clicked.connect(self.remove_camera)
        cam_btn_row.addWidget(self.btn_remove)
        controls.addLayout(cam_btn_row)
        
        self.cam_list = QListWidget()
        self.cam_list.setMaximumHeight(100)
        controls.addWidget(self.cam_list)
        
        # AI Detection Rules Section
        controls.addWidget(QLabel(""))  # Spacer
        controls.addWidget(QLabel("<b>AI Detection Rules</b>"))
        hint = QLabel("YOLO (local) + Loitering • Twelve Labs (cloud)")
        hint.setStyleSheet("color: #888; font-size: 10px;")
        controls.addWidget(hint)
        
        # Scenario dropdown
        self.scenario_combo = QComboBox()
        from rtstream_monitor import DetectionScenario, get_scenario_prompt
        for scenario in DetectionScenario:
            self.scenario_combo.addItem(scenario.value, scenario)
        self.scenario_combo.currentIndexChanged.connect(self.on_scenario_changed)
        controls.addWidget(self.scenario_combo)
        
        # Custom prompt
        controls.addWidget(QLabel("Detection Prompt:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMaximumHeight(60)
        self.prompt_edit.setPlaceholderText("e.g. 'person', 'loitering', 'cell phone'...")
        # Set initial prompt
        self.on_scenario_changed(0)
        controls.addWidget(self.prompt_edit)
        
        # Add Rule button
        rule_btn_row = QHBoxLayout()
        self.btn_add_rule = QPushButton("Add Rule")
        self.btn_add_rule.setIcon(qta.icon('fa5s.plus'))
        self.btn_add_rule.setStyleSheet("background-color: #2196F3;")
        self.btn_add_rule.clicked.connect(self.add_rule)
        rule_btn_row.addWidget(self.btn_add_rule)
        
        self.btn_remove_rule = QPushButton("Remove")
        self.btn_remove_rule.setIcon(qta.icon('fa5s.trash'))
        self.btn_remove_rule.clicked.connect(self.remove_rule)
        rule_btn_row.addWidget(self.btn_remove_rule)
        controls.addLayout(rule_btn_row)
        
        # Active Rules List
        controls.addWidget(QLabel("<b>Active Rules</b>"))
        self.rules_list = QListWidget()
        self.rules_list.setMaximumHeight(100)
        self.rules_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                color: #4CAF50;
                font-size: 11px;
            }
            QListWidget::item { padding: 3px; }
        """)
        controls.addWidget(self.rules_list)
        
        # Internal rules storage
        # Internal rules storage
        self.active_rules = []  # List of {id, scenario, prompt, enabled}
        self.selected_cam_id = None
        
        # Stream source for monitoring
        
        # Stream source for monitoring
        controls.addWidget(QLabel("Stream Source:"))
        self.stream_combo = QComboBox()
        self.stream_combo.setEditable(True)
        self.stream_combo.addItems([
            "rtsp://samples.rts.videodb.io:8554/floods",
            "Webcam (local only)",
            "Custom RTSP URL..."
        ])
        controls.addWidget(self.stream_combo)
        
        # Note about VideoDB
        note = QLabel("VideoDB requires RTSP. Webcam uses Local AI Demo.")
        note.setStyleSheet("color: #888; font-size: 10px;")
        controls.addWidget(note)
        
        # Webhook URL (optional)
        self.webhook_input = QLineEdit()
        self.webhook_input.setPlaceholderText("Webhook URL for alerts (optional)")
        controls.addWidget(self.webhook_input)
        
        # Control buttons
        monitor_btn_row = QHBoxLayout()
        self.btn_connect = QPushButton("Connect Stream")
        self.btn_connect.setIcon(qta.icon('fa5s.link'))
        self.btn_connect.clicked.connect(self.connect_stream)
        monitor_btn_row.addWidget(self.btn_connect)
        
        self.btn_start_monitor = QPushButton("Start Monitoring")
        self.btn_start_monitor.setIcon(qta.icon('fa5s.play'))
        self.btn_start_monitor.clicked.connect(self.start_monitoring)
        self.btn_start_monitor.setEnabled(False)
        monitor_btn_row.addWidget(self.btn_start_monitor)
        controls.addLayout(monitor_btn_row)
        
        self.btn_stop_monitor = QPushButton("Stop Monitoring")
        self.btn_stop_monitor.setIcon(qta.icon('fa5s.stop'))
        self.btn_stop_monitor.clicked.connect(self.stop_monitoring)
        self.btn_stop_monitor.setEnabled(False)
        controls.addWidget(self.btn_stop_monitor)
        
        # Deep Analyze button (Twelve Labs on-demand)
        self.btn_deep_analyze = QPushButton("Deep Analyze (Twelve Labs)")
        self.btn_deep_analyze.setIcon(qta.icon('fa5s.microscope'))
        self.btn_deep_analyze.setStyleSheet("background-color: #9C27B0; color: white; font-weight: bold;")
        self.btn_deep_analyze.clicked.connect(lambda: (print("[CLICK] Deep Analyze button pressed!"), self.deep_analyze()))
        self.btn_deep_analyze.setToolTip("Capture 5 sec clip and send to Twelve Labs for AI analysis")
        controls.addWidget(self.btn_deep_analyze)
        
        # Status
        self.monitor_status = QLabel("Not connected")
        self.monitor_status.setStyleSheet("color: #888;")
        controls.addWidget(self.monitor_status)
        
        controls.addStretch()
        main_layout.addLayout(controls, stretch=1)
        
        # RIGHT PANEL: Grid + Event Log
        right_panel = QVBoxLayout()
        
        # Camera Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_container.setLayout(self.grid_layout)
        scroll.setWidget(self.grid_container)
        right_panel.addWidget(scroll, stretch=2)
        
        # Event Log
        right_panel.addWidget(QLabel("<b>Detected Events</b>"))
        self.event_log = QTextEdit()
        self.event_log.setReadOnly(True)
        self.event_log.setMaximumHeight(150)
        self.event_log.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #4CAF50;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        right_panel.addWidget(self.event_log)
        
        # Refresh events button
        self.btn_refresh_events = QPushButton("Refresh Events")
        self.btn_refresh_events.setIcon(qta.icon('fa5s.sync'))
        self.btn_refresh_events.clicked.connect(self.refresh_events)
        self.btn_refresh_events.setEnabled(False)
        right_panel.addWidget(self.btn_refresh_events)
        
        main_layout.addLayout(right_panel, stretch=3)
        self.setLayout(main_layout)
    
    def on_scenario_changed(self, index):
        """Update prompt when scenario changes."""
        from rtstream_monitor import get_scenario_prompt
        scenario = self.scenario_combo.currentData()
        if scenario:
            self.prompt_edit.setText(get_scenario_prompt(scenario))
    
    def add_rule(self):
        """Add current scenario/prompt as a new rule."""
        scenario = self.scenario_combo.currentData()
        prompt = self.prompt_edit.toPlainText().strip()
        
        if not prompt:
            self.monitor_status.setText("Enter a detection prompt first")
            return
        
        # Create rule
        rule_id = len(self.active_rules) + 1
        rule = {
            'id': rule_id,
            'scenario': scenario.value if scenario else 'Custom',
            'prompt': prompt,
            'enabled': True
        }
        self.active_rules.append(rule)
        
        # Add to list widget with checkbox
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import Qt
        item = QListWidgetItem(f"[{rule['scenario']}] {prompt[:40]}...")
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        item.setData(Qt.UserRole, rule_id)
        self.rules_list.addItem(item)
        
        self.monitor_status.setText(f"Added rule: {rule['scenario']}")
        
        # Enable start if we have rules
        if len(self.active_rules) > 0:
            self.btn_start_monitor.setEnabled(True)
    
    def remove_rule(self):
        """Remove selected rule from the list."""
        item = self.rules_list.currentItem()
        if item:
            rule_id = item.data(Qt.UserRole)
            # Remove from internal list
            self.active_rules = [r for r in self.active_rules if r['id'] != rule_id]
            # Remove from widget
            self.rules_list.takeItem(self.rules_list.row(item))
            self.monitor_status.setText("🗑️ Rule removed")
            
            # Disable start if no rules
            if len(self.active_rules) == 0:
                self.btn_start_monitor.setEnabled(False)
    
    def connect_stream(self):
        """Connect to source (RTSP or Webcam Demo)."""
        source = self.stream_combo.currentText().strip()
        
        # LOCAL WEBCAM DEMO
        if "Webcam" in source:
            self.monitor_status.setText("✅ Demo Mode: Webcam Ready")
            self.current_stream_id = "webcam_demo"
            self.btn_start_monitor.setEnabled(True)
            self.btn_connect.setEnabled(False)
            return

        # VIDEODB RTSP
        if not source or "Custom" in source:
            self.monitor_status.setText("⚠️ Enter valid RTSP URL")
            return
            
        self.monitor_status.setText("Connecting to VideoDB...")
        
        try:
            from rtstream_monitor import RTStreamMonitor, StreamConfig, DetectionScenario
            
            # Initialize monitor if needed
            if not self.rtstream_monitor:
                self.rtstream_monitor = RTStreamMonitor(
                    api_key="sk-idjvWUi2BhlxJnCKaHFUIaKmrdFLWteLPb2OqHmNjzY"
                )
            
            scenario = self.scenario_combo.currentData() or DetectionScenario.CUSTOM
            config = StreamConfig(
                name=f"{scenario.value} Monitor",
                rtsp_url=source,
                scenario=scenario,
                custom_prompt=self.prompt_edit.toPlainText()
            )
            
            self.current_stream_id = self.rtstream_monitor.connect_stream(config)
            self.monitor_status.setText(f"✅ Connected: {self.current_stream_id[:15]}...")
            self.btn_start_monitor.setEnabled(True)
            self.btn_connect.setEnabled(False)
            
        except Exception as e:
            self.monitor_status.setText(f"❌ Error: {str(e)[:50]}")
    
    def start_monitoring(self):
        """Start AI monitoring."""
        # Check if rules list is populated
        if not self.active_rules:
            self.monitor_status.setText("⚠️ Add at least one rule first")
            return
            
        # For demo mode, don't require connect
        source = self.stream_combo.currentText().strip()
        if "Webcam" in source:
            self.current_stream_id = "webcam_demo"
        
        if not self.current_stream_id:
            self.monitor_status.setText("⚠️ Connect to a stream first")
            return
            
        from rtstream_monitor import StreamConfig, DetectionScenario
        
        # --- LOCAL DEMO MODE ---
        if self.current_stream_id == "webcam_demo":
            rule_count = len(self.active_rules)
            self.monitor_status.setText(f"🔴 LIVE (DEMO): {rule_count} rule(s) active")
            self.local_worker = LocalAIWorker(self.multi_cam, self.active_rules)
            self.local_worker.event_detected.connect(self.on_demo_event)
            self.local_worker.start()
            
            self.btn_start_monitor.setEnabled(False)
            self.btn_stop_monitor.setEnabled(True)
            self.btn_add_rule.setEnabled(False)
            self.btn_remove_rule.setEnabled(False)
            self.event_log.append(f"[INFO] Started Demo with {rule_count} active rules")
            return
            
        # --- VIDEODB MODE ---
        self.monitor_status.setText("Starting VideoDB AI...")
        
        try:
            config = StreamConfig(
                name=f"{scenario.value} Monitor",
                rtsp_url=self.stream_combo.currentText(),
                scenario=scenario,
                custom_prompt=self.prompt_edit.toPlainText(),
                webhook_url=self.webhook_input.text() or None
            )
            
            self.current_index_id = self.rtstream_monitor.start_monitoring(
                self.current_stream_id,
                config,
                on_status=lambda s: self.monitor_status.setText(s)
            )
            
            # Create event if webhook provided
            if config.webhook_url:
                event_id = self.rtstream_monitor.create_event(scenario, config.custom_prompt)
                alert_id = self.rtstream_monitor.create_alert(
                    self.current_index_id, event_id, config.webhook_url
                )
                self.event_log.append(f"[ALERT] Webhook configured: {alert_id[:20]}...")
            
            self.monitor_status.setText(f"🔴 LIVE: Monitoring for {scenario.value}")
            self.btn_start_monitor.setEnabled(False)
            self.btn_stop_monitor.setEnabled(True)
            self.btn_refresh_events.setEnabled(True)
            
            self.event_log.append(f"[INFO] Started VideoDB Index: {self.current_index_id}")
            
        except Exception as e:
            self.monitor_status.setText(f"Error: {str(e)[:50]}")
            self.event_log.append(f"[ERROR] {str(e)}")
    
    def on_demo_event(self, event_data):
        """Handle events from local demo worker."""
        desc = event_data['description']
        ts = event_data.get('timestamp', datetime.now().strftime("%H:%M:%S"))
        self.event_log.append(f"[{ts}] {desc}")
    
    def stop_monitoring(self):
        """Stop AI monitoring."""
        # Stop Local Demo
        if self.local_worker and self.local_worker.isRunning():
            self.local_worker.running = False
            self.local_worker.wait()
            self.local_worker = None
            self.event_log.append("[INFO] Stopped Demo Monitoring")
            
        # Stop VideoDB
        elif self.current_index_id and self.rtstream_monitor:
            try:
                self.rtstream_monitor.stop_monitoring(self.current_index_id)
                self.event_log.append(f"[INFO] Stopped VideoDB Monitoring")
            except Exception as e:
                self.event_log.append(f"[ERROR] {str(e)}")
        
        self.monitor_status.setText("Monitoring stopped")
        self.btn_start_monitor.setEnabled(len(self.active_rules) > 0)
        self.btn_stop_monitor.setEnabled(False)
        self.btn_connect.setEnabled(True)
        self.btn_add_rule.setEnabled(True)
        self.btn_remove_rule.setEnabled(True)
        self.current_stream_id = None
    
    def deep_analyze(self):
        """Capture webcam clip and analyze with Twelve Labs (Async)."""
        print("[DEBUG] Deep Analyze button clicked")
        print(f"[DEBUG] API Key present: {bool(TWELVE_LABS_API_KEY)}")
        
        if not TWELVE_LABS_API_KEY:
            self.monitor_status.setText("API Key Missing")
            QMessageBox.warning(self, "Missing API Key", "Please set TWELVE_LABS_API_KEY env var.")
            return

        self.btn_deep_analyze.setEnabled(False)
        self.monitor_status.setText("Starting Deep Analysis...")
        print("[DEBUG] Starting DeepAnalyzeWorker...")
        
        # Start Worker
        self.analyze_worker = DeepAnalyzeWorker(TWELVE_LABS_API_KEY)
        self.analyze_worker.status_update.connect(self.monitor_status.setText)
        self.analyze_worker.finished.connect(self.on_analyze_finished)
        self.analyze_worker.error.connect(self.on_analyze_error)
        self.analyze_worker.start()
        print("[DEBUG] Worker started")
        
    def on_analyze_finished(self, result: str):
        """Handle successful analysis."""
        self.btn_deep_analyze.setEnabled(True)
        self.monitor_status.setText("Analysis Complete")
        self.event_log.append(f"[DEEP ANALYZE] {result}")
        
    def on_analyze_error(self, error: str):
        """Handle analysis error."""
        self.btn_deep_analyze.setEnabled(True)
        self.monitor_status.setText(f"Error: {error}")
        self.event_log.append(f"[ERROR] Deep Analyze failed: {error}")
        

    
    def refresh_events(self):
        """Fetch and display recent detected events."""
        if not self.current_index_id or not self.rtstream_monitor:
            return
        
        try:
            scenes = self.rtstream_monitor.get_recent_scenes(self.current_index_id)
            if scenes:
                self.event_log.append(f"\n--- Recent Detections ({len(scenes)}) ---")
                for scene in scenes:
                    desc = scene.get('description', 'No description')[:80]
                    self.event_log.append(f"[SCENE] {desc}")
            else:
                self.event_log.append("[INFO] No new scenes detected yet")
        except Exception as e:
            self.event_log.append(f"[ERROR] {str(e)}")

    # ---- Original Camera Methods ----
    def add_camera(self):
        source = self.cam_input.text()
        if source:
            if cam_id:
                # Store ID in user data
                item = QListWidgetItem(cam_id)
                item.setData(Qt.UserRole, cam_id)
                self.cam_list.addItem(item)
                
                lbl = ClickableCameraWidget(cam_id, f"Loading {cam_id}...")
                lbl.setMinimumSize(320, 240)
                lbl.setSizePolicy(
                    self.cam_list.sizePolicy().horizontalPolicy(), 
                    self.cam_list.sizePolicy().verticalPolicy()
                )
                lbl.default_style = "background-color: gray; border: 1px solid white;"
                lbl.setStyleSheet(lbl.default_style)
                lbl.clicked.connect(self.select_camera)
                
                self.grid_widgets[cam_id] = lbl
                self.rebuild_grid()
    
    def add_webcam(self):
        """Add the default webcam (device 0) for demo purposes."""
        cam_id = self.multi_cam.add_camera(0)  # 0 = default webcam
        
        if cam_id is not None: # Check for None explicitly as 0 is falsey
            # Store ID in user data
            item = QListWidgetItem(f"Webcam ({cam_id})")
            item.setData(Qt.UserRole, cam_id)
            self.cam_list.addItem(item)
            
            lbl = ClickableCameraWidget(cam_id, "Webcam Loading...")
            lbl.setMinimumSize(320, 240)
            lbl.setSizePolicy(
                self.cam_list.sizePolicy().horizontalPolicy(), 
                self.cam_list.sizePolicy().verticalPolicy()
            )
            lbl.default_style = "background-color: #1a1a1a; border: 2px solid #4CAF50;"
            lbl.setStyleSheet(lbl.default_style)
            lbl.clicked.connect(self.select_camera)
            
            self.grid_widgets[cam_id] = lbl
            self.rebuild_grid()

    def add_dummy_camera(self):
        """Add a dummy camera for grid layout testing."""
        cam_id = f"dummy_{len(self.grid_widgets) + 1}_{int(datetime.now().timestamp())}"
        
        # Add to list
        item = QListWidgetItem(f"Demo Cam ({cam_id[-4:]})")
        item.setData(Qt.UserRole, cam_id)
        self.cam_list.addItem(item)
        
        # Create reactive looking widget
        lbl = ClickableCameraWidget(cam_id, f"DEMO CAMERA\n{cam_id}")
        lbl.setMinimumSize(320, 240)
        lbl.setSizePolicy(
            self.cam_list.sizePolicy().horizontalPolicy(), 
            self.cam_list.sizePolicy().verticalPolicy()
        )
        lbl.default_style = "background-color: #2b2b2b; color: #555; border: 2px solid #444; font-weight: bold;"
        lbl.setStyleSheet(lbl.default_style)
        lbl.clicked.connect(self.select_camera)
        
        self.grid_widgets[cam_id] = lbl
        self.rebuild_grid()

    def select_camera(self, cam_id):
        """Highlight selected camera and make it bigger."""
        self.selected_cam_id = cam_id
        
        # Reset stretches first (default 1)
        for r in range(self.grid_layout.rowCount()):
            self.grid_layout.setRowStretch(r, 1)
        for c in range(self.grid_layout.columnCount()):
            self.grid_layout.setColumnStretch(c, 1)
            
        # Update styles and stretches
        selected_row, selected_col = -1, -1
        
        for k, widget in self.grid_widgets.items():
            is_selected = (k == cam_id)
            if isinstance(widget, ClickableCameraWidget):
                widget.set_selected(is_selected)
            
            if is_selected:
                # Find position in grid
                idx = self.grid_layout.indexOf(widget)
                if idx >= 0:
                    selected_row, selected_col, _, _ = self.grid_layout.getItemPosition(idx)
        
        # Apply stretch factor 10 to the row/col of selected item (Huge difference)
        if selected_row >= 0 and selected_col >= 0:
            self.grid_layout.setRowStretch(selected_row, 10) # Make it DOMINANT
            self.grid_layout.setColumnStretch(selected_col, 10)

    def remove_camera(self):
        item = self.cam_list.currentItem()
        if item:
            # Use stored ID if available, else text
            cam_id = item.data(Qt.UserRole)
            if cam_id is None:
                cam_id = item.text()
                
            self.multi_cam.remove_camera(cam_id)
            self.cam_list.takeItem(self.cam_list.row(item))
            
            # Use string representation for dict lookup if needed
            # (multi_cam might use int 0, grid_widgets uses same key)
            
            if cam_id in self.grid_widgets:
                self.grid_layout.removeWidget(self.grid_widgets[cam_id])
                self.grid_widgets[cam_id].deleteLater()
                del self.grid_widgets[cam_id]
                self.rebuild_grid()

    def rebuild_grid(self):
        """Rebuild grid with dynamic flexible layout (up to N x N)."""
        # Clear layout first
        for i in reversed(range(self.grid_layout.count())): 
            item = self.grid_layout.itemAt(i)
            if item.widget():
                if item.widget() not in self.grid_widgets.values():
                    item.widget().deleteLater() # Delete placeholders
                else:
                    item.widget().setParent(None) # Remove camera from layout temporarily

        active_cams = list(self.grid_widgets.values())
        
        # Calculate optimal grid size
        # If 1-4 items -> 2x2. 5-9 -> 3x3. 10-16 -> 4x4.
        count = len(active_cams)
        cols = 2
        
        if count > 0:
            cols = math.ceil(math.sqrt(count))
            if cols < 2: cols = 2 # Minimum 2x2
            
        total_slots = cols * cols # Make it a perfect square
        
        for i in range(total_slots):
            row = i // cols
            col = i % cols
            
            if i < len(active_cams):
                self.grid_layout.addWidget(active_cams[i], row, col)
                active_cams[i].show()
            else:
                placeholder = QLabel("OFFLINE / NO SIGNAL")
                placeholder.setMinimumSize(320, 240) # Allow shrinking
                placeholder.setSizePolicy(
                    self.cam_list.sizePolicy().horizontalPolicy(), 
                    self.cam_list.sizePolicy().verticalPolicy()
                )
                placeholder.setStyleSheet("""
                    background-color: #0d0d0d; 
                    color: #333; 
                    border: 1px dashed #222; 
                    font-weight: bold;
                """)
                placeholder.setAlignment(Qt.AlignCenter)
                self.grid_layout.addWidget(placeholder, row, col)

    def update_grid(self):
        for cam_id, lbl in self.grid_widgets.items():
            frame = self.multi_cam.get_frame(cam_id)
            if frame is not None:
                lbl.setPixmap(convert_cv_qt(frame))


# ==================== SETTINGS TAB ====================
class SettingsTab(QWidget):
    """Settings & Account Management."""
    logout_requested = Signal()
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignTop)
        
        # --- Account Security ---
        sec_group = QGroupBox("Security Settings")
        sec_layout = QFormLayout()
        sec_layout.setSpacing(15)
        
        self.old_pass = QLineEdit()
        self.old_pass.setEchoMode(QLineEdit.Password)
        self.old_pass.setPlaceholderText("Current Password")
        sec_layout.addRow("Current Password:", self.old_pass)
        
        self.new_pass = QLineEdit()
        self.new_pass.setEchoMode(QLineEdit.Password)
        self.new_pass.setPlaceholderText("New Password")
        sec_layout.addRow("New Password:", self.new_pass)
        
        self.confirm_pass = QLineEdit()
        self.confirm_pass.setEchoMode(QLineEdit.Password)
        self.confirm_pass.setPlaceholderText("Confirm New Password")
        sec_layout.addRow("Confirm Password:", self.confirm_pass)
        
        self.btn_update = QPushButton("Update Password")
        self.btn_update.setIcon(qta.icon('fa5s.key', color='white'))
        self.btn_update.setStyleSheet("background-color: #0E639C; margin-top: 10px;")
        self.btn_update.clicked.connect(self.update_password)
        sec_layout.addRow("", self.btn_update)
        
        sec_group.setLayout(sec_layout)
        layout.addWidget(sec_group)
        
        # --- Session ---
        sess_group = QGroupBox("Session")
        sess_layout = QVBoxLayout()
        
        self.btn_logout = QPushButton("Logout")
        self.btn_logout.setIcon(qta.icon('fa5s.sign-out-alt', color='white'))
        self.btn_logout.setStyleSheet("background-color: #D32F2F; font-weight: bold; padding: 10px;")
        self.btn_logout.clicked.connect(self.logout_requested.emit)
        sess_layout.addWidget(self.btn_logout)
        
        sess_group.setLayout(sess_layout)
        layout.addWidget(sess_group)
        
        self.setLayout(layout)
        
    def update_password(self):
        old = self.old_pass.text()
        new = self.new_pass.text()
        confirm = self.confirm_pass.text()
        
        if not old or not new:
            QMessageBox.warning(self, "Error", "All fields are required")
            return
            
        if new != confirm:
            QMessageBox.warning(self, "Error", "New passwords do not match")
            return
            
        from auth_manager import get_auth_manager
        auth = get_auth_manager()
        
        # Verify old first
        # We assume current user is 'admin' for MVP or need to store current session user
        # For MVP, let's try to auth with 'admin' and old pass
        # Improve: Store logged in user in MainWindow
        user = "admin" 
        
        if not auth.authenticate(user, old):
             QMessageBox.critical(self, "Failed", "Current password is incorrect")
             return
             
        if auth.update_password(user, new):
            QMessageBox.information(self, "Success", "Password updated successfully")
            self.old_pass.clear()
            self.new_pass.clear()
            self.confirm_pass.clear()
        else:
            QMessageBox.critical(self, "Error", "Failed to update password")


# ==================== MAIN WINDOW ====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Metagros")
        self.setWindowIcon(QIcon())  # Remove default icon
        self.setGeometry(100, 100, 1400, 900)
        
        # Global Polished Stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', sans-serif; }
            
            /* Input Fields - Professional Dark Look */
            QLineEdit, QComboBox, QTextEdit {
                background-color: #252526;
                color: #E0E0E0;
                border: 1px solid #3E3E42;
                border-radius: 2px;
                padding: 6px;
                selection-background-color: #264F78;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #007ACC;
                background-color: #2D2D30;
            }
            QLineEdit:disabled, QComboBox:disabled {
                background-color: #1E1E1E;
                color: #555;
            }

            /* Buttons */
            QPushButton {
                background-color: #0E639C;
                color: white;
                border: none;
                padding: 6px 14px;
                border-radius: 2px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1177BB; }
            QPushButton:pressed { background-color: #094771; }
            QPushButton:disabled { background-color: #333; color: #888; }
            
            /* Group Boxes */
            QGroupBox {
                border: 1px solid #333;
                border-radius: 2px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #AAA;
            }
            
            /* Tabs */
            QTabWidget::pane { border: 1px solid #333; }
            QTabBar::tab {
                background: #1a1a1a;
                color: #888;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #252526;
                color: white;
                border-bottom: 2px solid #007ACC;
            }
        """)

        self.face_handler = FaceHandler()
        self.data_manager = DataManager()
        self.multi_cam = MultiCameraManager()
        
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        

        self.video_tab = VideoAnalysisTab()
        self.grid_tab = GridTab(self.multi_cam)
        self.settings_tab = SettingsTab()
        self.settings_tab.logout_requested.connect(self.on_logout)
        

        self.tabs.addTab(self.video_tab, qta.icon('fa5s.search'), "Video Analysis (AI)")
        self.tabs.addTab(self.grid_tab, qta.icon('fa5s.th'), "CCTV Grid")
        self.tabs.addTab(self.settings_tab, qta.icon('fa5s.cog'), "Settings")
        
        # Logout flag
        self.logout_triggered = False

    def on_logout(self):
        """Handle logout request."""
        reply = QMessageBox.question(self, 'Logout', 'Are you sure you want to logout?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.logout_triggered = True
            self.close()

    def closeEvent(self, event):
        self.multi_cam.stop()
        event.accept()


# ==================== LOGIN DIALOG ====================
class LoginDialog(QDialog):
    """Secure Login Dialog (Metagros/Palantir Style)."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("METAGROS | AUTH")
        self.setFixedSize(450, 450)  # Increased height to prevent cutoff
        self.setWindowFlags(Qt.FramelessWindowHint)  # Modern borderless
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Frame
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border: 2px solid #333;
                border-radius: 8px;
            }
        """)
        layout.addWidget(frame)
        
        flayout = QVBoxLayout(frame)
        flayout.setSpacing(20)
        flayout.setContentsMargins(40, 50, 40, 50)  # More vertical padding
        
        # Logo / Title
        title = QLabel("METAGROS")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #fff; letter-spacing: 4px; border: none; background: transparent; margin-bottom: 5px;")
        flayout.addWidget(title)
        
        subtitle = QLabel("KINETIC AWARENESS PLATFORM")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 11px; color: #888; letter-spacing: 2px; border: none; margin-bottom: 25px; background: transparent;")
        flayout.addWidget(subtitle)
        
        # User Input
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("OPERATOR ID")
        self.user_input.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                border: 1px solid #444;
                padding: 5px 10px;
                color: #fff;
                font-family: Consolas, monospace;
                min-height: 35px;
                margin-bottom: 5px;
            }
            QLineEdit:focus { border: 2px solid #4CAF50; background-color: #333; }
        """)
        flayout.addWidget(self.user_input)
        
        # Password Input
        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("ACCESS KEY")
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.pass_input.setStyleSheet(self.user_input.styleSheet())
        flayout.addWidget(self.pass_input)
        
        # Login Button
        self.btn_login = QPushButton("AUTHENTICATE")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: #fff;
                border: 1px solid #444;
                padding: 10px;
                font-weight: bold;
                letter-spacing: 1px;
                min-height: 40px;
            }
            QPushButton:hover { background-color: #4CAF50; color: #000; border: 1px solid #4CAF50; }
        """)
        self.btn_login.clicked.connect(self.authenticate)
        flayout.addWidget(self.btn_login)
        
        # Status
        self.status = QLabel("SECURE TERMINAL // OFFLINE")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("color: #444; font-size: 9px; border: none; margin-top: 10px;")
        flayout.addWidget(self.status)
        
        # Quit Button (X top right)
        # (Simplified: Just use Esc to close app if needed)

    def authenticate(self):
        username = self.user_input.text().strip()
        password = self.pass_input.text()
        
        if not username or not password:
            self.status.setText("CREDENTIALS REQUIRED")
            self.status.setStyleSheet("color: #FF5722; font-size: 9px; border: none;")
            return
            
        try:
            from auth_manager import get_auth_manager
            auth = get_auth_manager()
            if auth.authenticate(username, password):
                self.status.setText("ACCESS GRANTED")
                self.status.setStyleSheet("color: #4CAF50; font-size: 9px; border: none;")
                QTimer.singleShot(500, self.accept)  # Delay to show success
            else:
                self.status.setText("ACCESS DENIED")
                self.status.setStyleSheet("color: #F44336; font-size: 9px; border: none;")
                self.pass_input.clear()
        except Exception as e:
            self.status.setText(f"ERROR: {str(e)}")


# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Dark theme
    app.setStyleSheet("""
        QMainWindow, QWidget { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
        QGroupBox { font-weight: bold; border: 1px solid #333; border-radius: 4px; margin-top: 10px; padding-top: 10px; background-color: #1e1e1e; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #888; }
        QPushButton { background-color: #2d2d2d; border: 1px solid #444; padding: 6px 14px; border-radius: 2px; }
        QPushButton:hover { background-color: #3d3d3d; border-color: #666; }
        QPushButton:checked { background-color: #4CAF50; color: #000; border-color: #4CAF50; }
        QPushButton:disabled { background-color: #1a1a1a; color: #444; border-color: #222; }
        QLineEdit, QTextEdit, QComboBox { background-color: #2d2d2d; border: 1px solid #444; padding: 6px; border-radius: 2px; color: #fff; }
        QLineEdit:focus { border: 1px solid #555; }
        QTableWidget { background-color: #1e1e1e; gridline-color: #333; border: 1px solid #333; }
        QHeaderView::section { background-color: #2d2d2d; padding: 6px; border: 1px solid #333; font-weight: bold; }
        QTabWidget::pane { border: 1px solid #333; background-color: #1e1e1e; }
        QTabBar::tab { background-color: #1a1a1a; padding: 10px 25px; margin-right: 2px; color: #888; }
        QTabBar::tab:selected { background-color: #1e1e1e; color: #4CAF50; border-top: 2px solid #4CAF50; }
        QScrollBar:vertical { width: 10px; background: #121212; }
        QScrollBar::handle:vertical { background: #333; border-radius: 5px; }
    """)
    
    # Show Login First
    # Main Loop (to support Logout)
    while True:
        # Show Login First
        login = LoginDialog()
        if login.exec() == QDialog.Accepted:
            window = MainWindow()
            window.showMaximized()
            app.exec() # Block until window closes
            
            # Check if logout was triggered
            if hasattr(window, 'logout_triggered') and window.logout_triggered:
                continue # Loop back to Login
            else:
                break # Exit app
        else:
            sys.exit(0)
            
    sys.exit(0)
