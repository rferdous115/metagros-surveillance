import os
import cv2
import threading
import time


class Camera:
    def __init__(self, src=0):
        self.src = src
        self.cap = None
        self.grabbed = False
        self.frame = None
        self.running = False
        self.lock = threading.Lock()
        self.loop_speed = 0.03  # Default ~30 FPS sleep
        self.playback_speed = 1.0
        self.fps = 30.0
        self.thread = None  # Initialize thread attribute

    def start(self):
        if self.running:
            self.stop()
        
        # Check if source is integer (Webcam) or string (File)
        if isinstance(self.src, int):
            self.cap = cv2.VideoCapture(self.src)
            self.fps = 30.0
        else:
            # File Path
            print(f"[DEBUG] Opening video file: {self.src}")
            
            # WORKAROUND: Fix "Assertion async_lock failed" in FFmpeg/OpenCV
            os.environ["OPENCV_FFMPEG_THREADS"] = "1"
            os.environ["OPENCV_VIDEOIO_PRIORITY_MSMF"] = "0"
            
            self.cap = cv2.VideoCapture(self.src)
            
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30.0
        
        if not self.cap.isOpened():
            print(f"[ERROR] Critical: Could not open source {self.src}")
            self.running = False
            return self
            
        print(f"[DEBUG] Source opened successfully. FPS: {self.fps}")
        self.running = True
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()
        print(f"Camera started: {self.src}")
        return self

    def update(self):
        print(f"[DEBUG] Camera Update Loop Started for {self.src}")
        while self.running:
            if not self.cap.isOpened():
                print("[DEBUG] Camera not opened, retrying...")
                time.sleep(1.0)
                continue
                
            grabbed, frame = self.cap.read()
            
            if not grabbed:
                if not isinstance(self.src, int):
                    # End of file -> Loop
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

            with self.lock:
                self.grabbed = grabbed
                if grabbed:
                    self.frame = frame
            
            # Sleep based on FPS
            delay = 1.0 / (self.fps * self.playback_speed)
            time.sleep(max(0.001, delay))

    def set_seek(self, percent):
        # Only works for files
        if self.cap and not isinstance(self.src, int):
            total = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            target = int(total * (percent / 100.0))
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, target)

    def set_speed(self, speed):
        self.playback_speed = max(0.1, speed)

    def get_progress(self):
        # Returns current %
        if self.cap and not isinstance(self.src, int):
            total = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            current = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
            if total > 0:
                return (current / total) * 100.0
        return 0.0

    def get_frame(self):
        with self.lock:
            if self.grabbed:
                return self.frame.copy()
            return None

    def stop(self):
        self.running = False
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
