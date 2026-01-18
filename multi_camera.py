import cv2
import threading
import time
import numpy as np


class MultiCameraManager:
    """Manages multiple camera sources for grid display (Qt-only version)."""
    
    def __init__(self):
        self.cameras = {}  # {id: {"cap": VideoCapture, "url": url, "last_frame": frame}}
        self.lock = threading.Lock()
        self.running = True
        self.thread = None
        
        # Start updater thread
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

    def add_camera(self, source):
        """Add a camera source (webcam ID or RTSP URL)."""
        cam_id = f"cam_{len(self.cameras) + 1}_{int(time.time())}"
        
        print(f"Adding Camera: {source}")
        
        # Handle int source (webcam) or string that is a digit
        if isinstance(source, int) or (isinstance(source, str) and source.isdigit()):
            src_val = int(source) if isinstance(source, str) else source
            cap = cv2.VideoCapture(src_val, cv2.CAP_DSHOW)
        else:
            # RTSP or file path
            cap = cv2.VideoCapture(source)
            cap.set(cv2.CAP_PROP_THREAD_COUNT, 0)
            
        if not cap.isOpened():
            print(f"Failed to open camera: {source}")
            return None
        
        width = 640
        height = 480

        with self.lock:
            self.cameras[cam_id] = {
                "cap": cap,
                "url": source,
                "width": width,
                "height": height,
                "last_frame": None
            }
            
        return cam_id

    def remove_camera(self, cam_id):
        """Remove a camera by ID."""
        with self.lock:
            if cam_id in self.cameras:
                self.cameras[cam_id]["cap"].release()
                del self.cameras[cam_id]

    def update_loop(self):
        """Background thread that continuously reads frames from all cameras."""
        # Lazy load detector to avoid slowing startup
        detector = None
        
        while self.running:
            # Get list of camera IDs (snapshot to avoid lock contention)
            with self.lock:
                current_cams = list(self.cameras.keys())
            
            for cam_id in current_cams:
                try:
                    cam = None
                    with self.lock:
                        if cam_id in self.cameras:
                            cam = self.cameras[cam_id]
                    
                    if not cam:
                        continue
                    
                    grabbed, frame = cam["cap"].read()
                    if grabbed:
                        # Resize to thumbnail size
                        frame = cv2.resize(frame, (cam["width"], cam["height"]))
                        
                        # Run YOLO detection (lazy load)
                        detections = []
                        try:
                            if detector is None:
                                print("[MultiCamera] Loading YOLO detector...")
                                from object_detector import get_detector
                                detector = get_detector()
                                if detector and detector.model:
                                    print("[MultiCamera] YOLO detector ready!")
                                else:
                                    print("[MultiCamera] YOLO detector failed to load model")
                            
                            if detector and detector.model:
                                detections = detector.detect(frame)
                                if detections:
                                    print(f"[MultiCamera] Detected: {[d['class'] for d in detections]}")
                                frame = detector.draw_boxes(frame, detections)
                        except Exception as e:
                            print(f"[MultiCamera] Detection error: {e}")
                        
                        # Draw restricted zones on frame
                        try:
                            from zone_manager import get_zone_manager
                            zone_mgr = get_zone_manager()
                            frame = zone_mgr.draw_zones(frame)
                        except:
                            pass  # Zone drawing is optional
                        
                        # Store frame and detections for Qt consumption
                        with self.lock:
                            if cam_id in self.cameras:
                                self.cameras[cam_id]["last_frame"] = frame
                                self.cameras[cam_id]["detections"] = detections
                    else:
                        # Loop video files
                        if not str(cam["url"]).isdigit():
                            cam["cap"].set(cv2.CAP_PROP_POS_FRAMES, 0)
                            
                except Exception as e:
                    print(f"Camera {cam_id} error: {e}")
            
            time.sleep(0.05)  # ~20 FPS (slightly slower to allow detection)

    def get_frame(self, cam_id):
        """Get the latest frame for a camera (thread-safe)."""
        with self.lock:
            if cam_id in self.cameras:
                frame = self.cameras[cam_id].get("last_frame")
                return frame.copy() if frame is not None else None
        return None

    def stop(self):
        """Stop all cameras and the update thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        with self.lock:
            for cam_id, cam in self.cameras.items():
                cam["cap"].release()
            self.cameras.clear()
