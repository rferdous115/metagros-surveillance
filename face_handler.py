try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    print("[Warning] face_recognition not installed - face detection disabled")
import cv2
import pickle
import os
import numpy as np


class FaceHandler:
    def __init__(self, db_path="faces.pkl"):
        self.db_path = db_path
        self.known_face_encodings = []
        self.known_face_names = []
        self.load_database()

    def load_database(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'rb') as f:
                    data = pickle.load(f)
                    self.known_face_encodings = data.get("encodings", [])
                    self.known_face_names = data.get("names", [])
                    print(f"Loaded {len(self.known_face_names)} faces from database.")
            except Exception as e:
                print(f"Error loading face database: {e}")

    def save_database(self):
        data = {
            "encodings": self.known_face_encodings,
            "names": self.known_face_names
        }
        with open(self.db_path, 'wb') as f:
            pickle.dump(data, f)

    def process_frame(self, frame):
        """Process a frame for face detection and recognition.
        
        Args:
            frame: BGR image (numpy array)
            
        Returns:
            tuple: (face_locations, face_names, face_encodings)
                   - face_locations are scaled back to original frame size
        """
        if not FACE_RECOGNITION_AVAILABLE:
            return [], [], []
            
        # Resize for speed
        scale = 0.5
        small_frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        # Detect faces
        face_locations = face_recognition.face_locations(rgb_small_frame)
        
        # Sort by 'left' coordinate for consistent ID ordering
        face_locations.sort(key=lambda x: x[3])

        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        face_names = []
        for face_encoding in face_encodings:
            name = "Unknown"
            if self.known_face_encodings:
                matches = face_recognition.compare_faces(
                    self.known_face_encodings, face_encoding, tolerance=0.45
                )
                face_distances = face_recognition.face_distance(
                    self.known_face_encodings, face_encoding
                )
                
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = self.known_face_names[best_match_index]
            
            face_names.append(name)

        # Scale locations back up
        scaled_locations = []
        inv_scale = int(1 / scale)
        for (top, right, bottom, left) in face_locations:
            top *= inv_scale
            right *= inv_scale
            bottom *= inv_scale
            left *= inv_scale
            scaled_locations.append((top, right, bottom, left))

        return scaled_locations, face_names, face_encodings

    def register_face(self, name, encoding):
        self.known_face_encodings.append(encoding)
        self.known_face_names.append(name)
        self.save_database()
        print(f"Registered new face: {name}")

    def rename_face(self, old_name, new_name):
        if old_name in self.known_face_names:
            indices = [i for i, x in enumerate(self.known_face_names) if x == old_name]
            for i in indices:
                self.known_face_names[i] = new_name
            self.save_database()
            return True
        return False
