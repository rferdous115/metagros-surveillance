"""
Zone Intrusion Detection

Allows users to define restricted zones and detect when persons enter them.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

@dataclass
class Zone:
    name: str
    points: List[Tuple[int, int]]  # Polygon vertices [(x1,y1), (x2,y2), ...]
    enabled: bool = True
    color: Tuple[int, int, int] = (0, 0, 255)  # Red by default
    
    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside the polygon using ray casting."""
        n = len(self.points)
        if n < 3:
            return False
        inside = False
        p1x, p1y = self.points[0]
        for i in range(1, n + 1):
            p2x, p2y = self.points[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

class ZoneManager:
    """Manages restricted zones and checks for intrusions."""
    
    def __init__(self):
        self.zones: Dict[str, Zone] = {}
        self.intrusion_cooldown: Dict[str, float] = {}  # zone_name -> last_alert_time
        self.cooldown_seconds = 10.0  # Don't alert again for 10 seconds
    
    def add_zone(self, name: str, points: List[Tuple[int, int]], color=(0,0,255)) -> Zone:
        zone = Zone(name=name, points=points, color=color)
        self.zones[name] = zone
        return zone
    
    def remove_zone(self, name: str):
        if name in self.zones:
            del self.zones[name]
    
    def check_intrusions(self, detections: List[Dict]) -> List[Dict]:
        """Check if any person detection is inside a zone."""
        import time
        intrusions = []
        now = time.time()
        
        for det in detections:
            if det['class'] != 'person':
                continue
            x1, y1, x2, y2 = det['bbox']
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2  # Center point
            
            for zone_name, zone in self.zones.items():
                if not zone.enabled:
                    continue
                if zone.contains_point(cx, cy):
                    # Check cooldown
                    last = self.intrusion_cooldown.get(zone_name, 0)
                    if now - last > self.cooldown_seconds:
                        intrusions.append({
                            'zone': zone_name,
                            'detection': det,
                            'center': (cx, cy)
                        })
                        self.intrusion_cooldown[zone_name] = now
        return intrusions
    
    def draw_zones(self, frame):
        """Draw all zones on a frame."""
        import cv2
        import numpy as np
        for zone_name, zone in self.zones.items():
            if not zone.enabled or len(zone.points) < 3:
                continue
            pts = np.array(zone.points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], True, zone.color, 2)
            # Draw zone name
            if zone.points:
                cv2.putText(frame, zone_name, zone.points[0], 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone.color, 1)
        return frame
    
    def get_zones(self) -> List[Zone]:
        return list(self.zones.values())

# Global instance
_zone_manager: Optional[ZoneManager] = None

def get_zone_manager() -> ZoneManager:
    global _zone_manager
    if _zone_manager is None:
        _zone_manager = ZoneManager()
    return _zone_manager
