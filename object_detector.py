"""
Real-time Object Detection using YOLOv8

Provides object detection with bounding boxes for the webcam feed.
Detects 80+ object classes (person, car, phone, etc.)
"""

import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple


class ObjectDetector:
    """YOLOv8-based object detector with bounding box drawing."""
    
    # COCO class names (80 classes)
    CLASSES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
        'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
        'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
        'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
        'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
        'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
        'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
        'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
        'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
        'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
        'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
        'toothbrush'
    ]
    
    # Colors for different classes (BGR format)
    COLORS = {
        'person': (0, 255, 0),       # Green
        'cell phone': (255, 0, 255), # Magenta
        'knife': (0, 0, 255),        # Red (danger)
        'car': (255, 255, 0),        # Cyan
        'bottle': (0, 255, 255),     # Yellow
        'default': (0, 255, 0)       # Green
    }
    
    def __init__(self, model_name: str = "yolov8n.pt", confidence: float = 0.5):
        """
        Initialize the detector.
        
        Args:
            model_name: YOLOv8 model to use (yolov8n.pt = nano, fastest)
            confidence: Minimum confidence threshold
        """
        self.confidence = confidence
        self.model = None
        self._load_model(model_name)
    
    def _load_model(self, model_name: str):
        """Load the YOLO model."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_name)
            print(f"[ObjectDetector] Loaded {model_name}")
        except Exception as e:
            print(f"[ObjectDetector] Failed to load model: {e}")
            self.model = None
    
    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        Detect objects in a frame.
        
        Returns:
            List of detections: [{class, confidence, bbox: (x1, y1, x2, y2)}]
        """
        if self.model is None or frame is None:
            return []
        
        try:
            # Run inference (verbose=False to suppress output)
            results = self.model(frame, verbose=False, conf=self.confidence)
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                    
                for box in boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    class_name = self.CLASSES[cls_id] if cls_id < len(self.CLASSES) else "unknown"
                    
                    detections.append({
                        'class': class_name,
                        'confidence': conf,
                        'bbox': (int(x1), int(y1), int(x2), int(y2))
                    })
            
            return detections
            
        except Exception as e:
            print(f"[ObjectDetector] Detection error: {e}")
            return []
    
    def draw_boxes(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame.
        
        Args:
            frame: Original frame
            detections: List of detection dicts
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for det in detections:
            x1, y1, x2, y2 = det['bbox']
            class_name = det['class']
            conf = det['confidence']
            
            # Get color for this class
            color = self.COLORS.get(class_name, self.COLORS['default'])
            
            # Draw box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label background
            label = f"{class_name} {conf:.2f}"
            (label_w, label_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, y1 - label_h - 10), (x1 + label_w + 5, y1), color, -1)
            
            # Draw label text
            cv2.putText(annotated, label, (x1 + 2, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        return annotated
    
    def detect_and_draw(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Dict]]:
        """
        Convenience method: detect and draw in one call.
        
        Returns:
            (annotated_frame, detections)
        """
        detections = self.detect(frame)
        annotated = self.draw_boxes(frame, detections)
        return annotated, detections


# Global detector instance (singleton pattern for efficiency)
_detector: Optional[ObjectDetector] = None


def get_detector() -> ObjectDetector:
    """Get or create the global detector instance."""
    global _detector
    if _detector is None:
        _detector = ObjectDetector()
    return _detector


def detect_objects(frame: np.ndarray) -> Tuple[np.ndarray, List[Dict]]:
    """
    Convenience function: Detect objects and draw boxes.
    
    Returns:
        (annotated_frame, detections)
    """
    detector = get_detector()
    return detector.detect_and_draw(frame)
