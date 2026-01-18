"""
Person Tracker with Loitering Detection

Tracks individuals across frames and detects loitering behavior
(person staying in same area for extended period).
"""

import time
import math
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class TrackedPerson:
    """Represents a tracked individual."""
    id: int
    positions: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, timestamp)
    last_seen: float = 0.0
    loitering_alerted: bool = False
    
    def add_position(self, x: float, y: float):
        """Add a new position with timestamp."""
        now = time.time()
        self.positions.append((x, y, now))
        self.last_seen = now
        
        # Keep only last 60 seconds of history
        cutoff = now - 60
        self.positions = [(px, py, pt) for px, py, pt in self.positions if pt > cutoff]
    
    def get_center(self) -> Tuple[float, float]:
        """Get current center position."""
        if not self.positions:
            return (0, 0)
        return (self.positions[-1][0], self.positions[-1][1])
    
    def get_movement_distance(self, seconds: float = 30.0) -> float:
        """
        Calculate total movement distance over the last N seconds.
        Low distance = potential loitering.
        """
        if len(self.positions) < 2:
            return 0.0
        
        now = time.time()
        cutoff = now - seconds
        recent = [(x, y) for x, y, t in self.positions if t > cutoff]
        
        if len(recent) < 2:
            return 0.0
        
        # Calculate total distance traveled
        total_dist = 0.0
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            dy = recent[i][1] - recent[i-1][1]
            total_dist += math.sqrt(dx*dx + dy*dy)
        
        return total_dist
    
    def get_bounding_box_size(self, seconds: float = 30.0) -> float:
        """
        Calculate the bounding box of positions over time.
        Small box = stayed in same area = loitering.
        """
        now = time.time()
        cutoff = now - seconds
        recent = [(x, y) for x, y, t in self.positions if t > cutoff]
        
        if len(recent) < 5:  # Need enough data points
            return float('inf')
        
        xs = [p[0] for p in recent]
        ys = [p[1] for p in recent]
        
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        
        return max(width, height)  # Return larger dimension
    
    def time_tracked(self) -> float:
        """How long has this person been tracked."""
        if not self.positions:
            return 0.0
        return time.time() - self.positions[0][2]


class PersonTracker:
    """
    Tracks multiple people across frames using centroid matching.
    Detects loitering behavior.
    """
    
    def __init__(self, 
                 max_distance: float = 100.0,
                 loiter_time: float = 30.0,
                 loiter_radius: float = 80.0,
                 expire_time: float = 5.0):
        """
        Args:
            max_distance: Max pixels to match person between frames
            loiter_time: Seconds before considered loitering
            loiter_radius: Max movement (pixels) to count as loitering
            expire_time: Seconds before unmatched person is removed
        """
        self.tracks: Dict[int, TrackedPerson] = {}
        self.next_id = 1
        self.max_distance = max_distance
        self.loiter_time = loiter_time
        self.loiter_radius = loiter_radius
        self.expire_time = expire_time
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """
        Update tracker with new detections.
        
        Args:
            detections: List of YOLO detections [{class, confidence, bbox}]
            
        Returns:
            List of tracked persons with loitering status
        """
        # Filter to only person detections
        person_detections = [d for d in detections if d['class'] == 'person']
        
        # Calculate centroids of detected persons
        centroids = []
        for det in person_detections:
            x1, y1, x2, y2 = det['bbox']
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            centroids.append((cx, cy, det))
        
        # Match centroids to existing tracks
        used_tracks = set()
        used_detections = set()
        
        # First pass: match existing tracks to nearest centroid
        for track_id, track in self.tracks.items():
            tx, ty = track.get_center()
            best_dist = float('inf')
            best_idx = -1
            
            for i, (cx, cy, det) in enumerate(centroids):
                if i in used_detections:
                    continue
                dist = math.sqrt((tx - cx)**2 + (ty - cy)**2)
                if dist < best_dist and dist < self.max_distance:
                    best_dist = dist
                    best_idx = i
            
            if best_idx >= 0:
                cx, cy, det = centroids[best_idx]
                track.add_position(cx, cy)
                used_tracks.add(track_id)
                used_detections.add(best_idx)
        
        # Create new tracks for unmatched detections
        for i, (cx, cy, det) in enumerate(centroids):
            if i not in used_detections:
                new_track = TrackedPerson(id=self.next_id)
                new_track.add_position(cx, cy)
                self.tracks[self.next_id] = new_track
                self.next_id += 1
        
        # Remove expired tracks
        now = time.time()
        expired = [tid for tid, t in self.tracks.items() 
                   if now - t.last_seen > self.expire_time]
        for tid in expired:
            del self.tracks[tid]
        
        # Build results with loitering detection
        results = []
        for track_id, track in self.tracks.items():
            is_loitering = self._check_loitering(track)
            
            results.append({
                'id': track_id,
                'position': track.get_center(),
                'time_tracked': track.time_tracked(),
                'is_loitering': is_loitering,
                'loitering_alerted': track.loitering_alerted
            })
            
            # Mark as alerted to avoid duplicate notifications
            if is_loitering and not track.loitering_alerted:
                track.loitering_alerted = True
        
        return results
    
    def _check_loitering(self, track: TrackedPerson) -> bool:
        """Check if a tracked person is loitering."""
        # Need to be tracked for at least loiter_time
        if track.time_tracked() < self.loiter_time:
            return False
        
        # Check if movement is below threshold
        bbox_size = track.get_bounding_box_size(self.loiter_time)
        
        return bbox_size < self.loiter_radius
    
    def get_loitering_persons(self) -> List[TrackedPerson]:
        """Get list of persons currently loitering."""
        return [t for t in self.tracks.values() 
                if self._check_loitering(t)]
    
    def get_person_count(self) -> int:
        """Get current number of tracked persons."""
        return len(self.tracks)


# Global tracker instance
_tracker: Optional[PersonTracker] = None


def get_tracker() -> PersonTracker:
    """Get or create global tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PersonTracker(
            loiter_time=15.0,   # 15 seconds for demo (adjust for production)
            loiter_radius=100.0  # pixels
        )
    return _tracker


# ==================== VEHICLE TRACKER ====================
class VehicleTracker:
    """
    Tracks vehicles across frames and detects parked/loitering vehicles.
    """
    
    VEHICLE_CLASSES = {'car', 'truck', 'bus', 'motorcycle'}
    
    def __init__(self, 
                 max_distance: float = 150.0,
                 loiter_time: float = 20.0,
                 loiter_radius: float = 50.0,
                 expire_time: float = 10.0):
        self.tracks: Dict[int, TrackedPerson] = {}  # Reuse TrackedPerson for simplicity
        self.next_id = 1000  # Start at 1000 to differentiate from persons
        self.max_distance = max_distance
        self.loiter_time = loiter_time
        self.loiter_radius = loiter_radius
        self.expire_time = expire_time
    
    def update(self, detections: List[Dict]) -> List[Dict]:
        """Update with new detections, returns tracked vehicles with loitering status."""
        vehicle_detections = [d for d in detections if d['class'] in self.VEHICLE_CLASSES]
        
        centroids = []
        for det in vehicle_detections:
            x1, y1, x2, y2 = det['bbox']
            cx = (x1 + x2) / 2
            cy = (y1 + y2) / 2
            centroids.append((cx, cy, det))
        
        used_tracks = set()
        used_detections = set()
        
        for track_id, track in self.tracks.items():
            tx, ty = track.get_center()
            best_dist = float('inf')
            best_idx = -1
            
            for i, (cx, cy, det) in enumerate(centroids):
                if i in used_detections:
                    continue
                dist = math.sqrt((tx - cx)**2 + (ty - cy)**2)
                if dist < best_dist and dist < self.max_distance:
                    best_dist = dist
                    best_idx = i
            
            if best_idx >= 0:
                cx, cy, det = centroids[best_idx]
                track.add_position(cx, cy)
                used_tracks.add(track_id)
                used_detections.add(best_idx)
        
        for i, (cx, cy, det) in enumerate(centroids):
            if i not in used_detections:
                new_track = TrackedPerson(id=self.next_id)
                new_track.add_position(cx, cy)
                self.tracks[self.next_id] = new_track
                self.next_id += 1
        
        now = time.time()
        expired = [tid for tid, t in self.tracks.items() 
                   if now - t.last_seen > self.expire_time]
        for tid in expired:
            del self.tracks[tid]
        
        results = []
        for track_id, track in self.tracks.items():
            is_parked = self._check_parked(track)
            
            results.append({
                'id': track_id,
                'position': track.get_center(),
                'time_tracked': track.time_tracked(),
                'is_loitering': is_parked,
                'loitering_alerted': track.loitering_alerted,
                'type': 'vehicle'
            })
            
            if is_parked and not track.loitering_alerted:
                track.loitering_alerted = True
        
        return results
    
    def _check_parked(self, track: TrackedPerson) -> bool:
        """Check if vehicle is parked (stationary for extended time)."""
        if track.time_tracked() < self.loiter_time:
            return False
        bbox_size = track.get_bounding_box_size(self.loiter_time)
        return bbox_size < self.loiter_radius


_vehicle_tracker: Optional[VehicleTracker] = None


def get_vehicle_tracker() -> VehicleTracker:
    """Get or create global vehicle tracker instance."""
    global _vehicle_tracker
    if _vehicle_tracker is None:
        _vehicle_tracker = VehicleTracker(
            loiter_time=20.0,   # 20 seconds for vehicles
            loiter_radius=50.0  # Vehicles move less when parked
        )
    return _vehicle_tracker
