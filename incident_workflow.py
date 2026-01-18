"""
Incident Workflow Module

Handles query expansion, moment merging, and report generation for security incidents.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class IncidentType(Enum):
    UNAUTHORIZED_ACCESS = "Unauthorized Access"
    TAILGATING = "Tailgating"
    LOITERING = "Loitering"
    SUSPICIOUS_OBJECT = "Suspicious Object Left Behind"
    FIGHT_ASSAULT = "Fight / Assault"
    AFTER_HOURS = "After-Hours Presence"
    SHOPLIFTING = "Shoplifting / Concealment"
    CUSTOM = "Custom Query"


# Query expansion: incident type -> list of search queries
INCIDENT_QUERIES: Dict[IncidentType, List[str]] = {
    IncidentType.UNAUTHORIZED_ACCESS: [
        "person entering restricted area without authorization",
        "unauthorized entry through door",
        "person bypassing security checkpoint",
        "intruder in secure zone",
        "person without badge entering building",
    ],
    IncidentType.TAILGATING: [
        "person follows another person through a door without swiping",
        "two people enter at once through a secure door",
        "unauthorized entry behind someone",
        "person slipping through door behind employee",
        "tailgating at entrance",
    ],
    IncidentType.LOITERING: [
        "person standing idle near entrance",
        "person lingering in hallway",
        "suspicious person waiting outside",
        "person loitering near door",
        "person standing around doing nothing",
    ],
    IncidentType.SUSPICIOUS_OBJECT: [
        "person leaves a bag",
        "unattended backpack",
        "abandoned package",
        "person drops object and walks away",
        "suspicious package left behind",
    ],
    IncidentType.FIGHT_ASSAULT: [
        "people fighting",
        "physical altercation",
        "violent confrontation",
        "person attacking another",
        "aggressive behavior between people",
    ],
    IncidentType.AFTER_HOURS: [
        "person walking in building at night",
        "intruder after closing hours",
        "movement in empty building",
        "person in office after hours",
        "late night unauthorized presence",
    ],
    IncidentType.SHOPLIFTING: [
        "person concealing merchandise",
        "shoplifting in store",
        "person hiding product in bag",
        "theft in progress",
        "person stealing item",
    ],
    IncidentType.CUSTOM: [],  # Relies entirely on user input
}


@dataclass
class EvidenceClip:
    """A single evidence clip with timestamp and metadata."""
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float  # 0.0 - 1.0
    label: str
    query_matched: str
    included: bool = True
    notes: str = ""
    video_id: str = ""
    
    @property
    def start_formatted(self) -> str:
        """Format start time as mm:ss"""
        mins = int(self.start_time // 60)
        secs = int(self.start_time % 60)
        return f"{mins:02d}:{secs:02d}"
    
    @property
    def end_formatted(self) -> str:
        """Format end time as mm:ss"""
        mins = int(self.end_time // 60)
        secs = int(self.end_time % 60)
        return f"{mins:02d}:{secs:02d}"
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class IncidentReport:
    """Structured incident report."""
    incident_type: str
    location: str
    camera_id: str
    time_range: str
    created_at: str
    executive_summary: List[str]
    timeline: List[Dict]
    evidence: List[EvidenceClip]
    recommended_actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "incident_type": self.incident_type,
            "location": self.location,
            "camera_id": self.camera_id,
            "time_range": self.time_range,
            "created_at": self.created_at,
            "executive_summary": self.executive_summary,
            "timeline": self.timeline,
            "evidence": [asdict(e) for e in self.evidence],
            "recommended_actions": self.recommended_actions,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class IncidentWorkflow:
    """Main workflow class for incident detection and reporting."""
    
    MERGE_GAP = 2.0  # seconds - merge clips within this gap
    MAX_CLIP_LENGTH = 15.0  # seconds
    PADDING = 1.0  # seconds to add before/after clips
    
    def __init__(self, sensitivity: str = "Medium"):
        """Initialize workflow with sensitivity level."""
        self.sensitivity = sensitivity
        self.top_k = {"Low": 3, "Medium": 5, "High": 10}.get(sensitivity, 5)
    
    def get_queries(self, incident_type: IncidentType, custom_query: Optional[str] = None) -> List[str]:
        """Get expanded queries for an incident type."""
        queries = INCIDENT_QUERIES.get(incident_type, []).copy()
        if custom_query and custom_query.strip():
            queries.append(custom_query.strip())
        return queries
    
    def merge_moments(self, moments: List[Dict], video_duration: float = float('inf')) -> List[EvidenceClip]:
        """Merge overlapping/nearby moments and create evidence clips."""
        if not moments:
            return []
        
        # Sort by start time
        sorted_moments = sorted(moments, key=lambda m: m.get('start', 0))
        
        merged = []
        current = None
        
        for m in sorted_moments:
            start = max(0, m.get('start', 0) - self.PADDING)
            end = min(video_duration, m.get('end', start + 5) + self.PADDING)
            confidence = m.get('confidence', m.get('score', 0.5))
            query = m.get('query', '')
            label = m.get('label', self._generate_label(query))
            video_id = m.get('video_id', '')
            
            if current is None:
                current = {
                    'start': start, 'end': end, 'confidence': confidence,
                    'query': query, 'label': label, 'video_id': video_id
                }
            elif start <= current['end'] + self.MERGE_GAP:
                # Merge: extend end, keep higher confidence
                current['end'] = max(current['end'], end)
                current['confidence'] = max(current['confidence'], confidence)
                # Append query if different
                if query and query not in current['query']:
                    current['query'] += f"; {query}"
            else:
                # Finalize current and start new
                merged.append(self._finalize_clip(current))
                current = {
                    'start': start, 'end': end, 'confidence': confidence,
                    'query': query, 'label': label, 'video_id': video_id
                }
        
        if current:
            merged.append(self._finalize_clip(current))
        
        return merged
    
    def _finalize_clip(self, clip_data: Dict) -> EvidenceClip:
        """Create EvidenceClip, splitting if too long."""
        duration = clip_data['end'] - clip_data['start']
        
        # If clip is too long, trim to max length (keeping start)
        if duration > self.MAX_CLIP_LENGTH:
            clip_data['end'] = clip_data['start'] + self.MAX_CLIP_LENGTH
        
        return EvidenceClip(
            start_time=clip_data['start'],
            end_time=clip_data['end'],
            confidence=clip_data['confidence'],
            label=clip_data['label'],
            query_matched=clip_data['query'],
            video_id=clip_data.get('video_id', '')
        )
    
    def _generate_label(self, query: str) -> str:
        """Generate a short label from the query."""
        if not query:
            return "Suspicious activity detected"
        
        # Simple heuristic: take first few words
        words = query.split()[:6]
        label = ' '.join(words)
        if len(query.split()) > 6:
            label += "..."
        return label.capitalize()
    
    def generate_report(
        self,
        incident_type: IncidentType,
        evidence: List[EvidenceClip],
        location: str = "",
        camera_id: str = "",
        analysis_text: Optional[str] = None
    ) -> IncidentReport:
        """Generate a structured incident report from evidence clips."""
        
        included = [e for e in evidence if e.included]
        
        if not included:
            return self._empty_report(incident_type, location, camera_id)
        
        # Calculate time range
        min_time = min(e.start_time for e in included)
        max_time = max(e.end_time for e in included)
        time_range = f"{self._format_time(min_time)} - {self._format_time(max_time)}"
        
        # Generate executive summary
        summary = self._generate_summary(incident_type, included, analysis_text)
        
        # Generate timeline
        timeline = [
            {
                "time": f"{e.start_formatted} - {e.end_formatted}",
                "event": e.label,
                "notes": e.notes
            }
            for e in sorted(included, key=lambda x: x.start_time)
        ]
        
        # Recommended actions
        actions = self._get_recommended_actions(incident_type)
        
        return IncidentReport(
            incident_type=incident_type.value,
            location=location or "Not specified",
            camera_id=camera_id or "Not specified",
            time_range=time_range,
            created_at=datetime.now().isoformat(),
            executive_summary=summary,
            timeline=timeline,
            evidence=included,
            recommended_actions=actions
        )
    
    def _generate_summary(
        self,
        incident_type: IncidentType,
        evidence: List[EvidenceClip],
        analysis_text: Optional[str] = None
    ) -> List[str]:
        """Generate executive summary bullets."""
        summary = []
        
        # Count and describe
        count = len(evidence)
        total_duration = sum(e.duration for e in evidence)
        avg_confidence = sum(e.confidence for e in evidence) / count if count else 0
        
        summary.append(f"Detected {count} potential {incident_type.value.lower()} incident(s)")
        summary.append(f"Total evidence duration: {total_duration:.1f} seconds")
        summary.append(f"Average confidence score: {avg_confidence:.0%}")
        
        # Add specific details based on labels
        unique_labels = set(e.label for e in evidence[:3])
        if unique_labels:
            summary.append(f"Key observations: {', '.join(unique_labels)}")
        
        # Add analysis text summary if available
        if analysis_text:
            # Take first sentence of analysis
            first_sentence = analysis_text.split('.')[0]
            if first_sentence:
                summary.append(f"AI Analysis: {first_sentence.strip()}")
        
        return summary
    
    def _get_recommended_actions(self, incident_type: IncidentType) -> List[str]:
        """Get recommended actions based on incident type."""
        actions = {
            IncidentType.UNAUTHORIZED_ACCESS: [
                "Review access control logs",
                "Verify identity of individual",
                "Consider security system upgrade"
            ],
            IncidentType.TAILGATING: [
                "Reinforce tailgating policy with employees",
                "Consider adding mantrap or turnstile",
                "Review badge access procedures"
            ],
            IncidentType.LOITERING: [
                "Dispatch security for welfare check",
                "Review historical footage for pattern",
                "Consider additional lighting or signage"
            ],
            IncidentType.SUSPICIOUS_OBJECT: [
                "Do NOT approach the object",
                "Evacuate area if necessary",
                "Contact local authorities immediately"
            ],
            IncidentType.FIGHT_ASSAULT: [
                "Contact emergency services immediately",
                "Preserve video evidence",
                "File incident report with HR/management"
            ],
            IncidentType.AFTER_HOURS: [
                "Verify if authorized personnel",
                "Check building access logs",
                "Confirm with facility management"
            ],
            IncidentType.SHOPLIFTING: [
                "Do not confront directly",
                "Gather evidence from video",
                "Contact loss prevention / authorities"
            ],
            IncidentType.CUSTOM: [
                "Review findings based on custom query",
                "Verify if alert matches security policy",
                "Log incident if verified"
            ],
        }
        return actions.get(incident_type, ["Review footage and assess situation"])
    
    def _empty_report(self, incident_type: IncidentType, location: str, camera_id: str) -> IncidentReport:
        """Generate empty report when no evidence included."""
        return IncidentReport(
            incident_type=incident_type.value,
            location=location or "Not specified",
            camera_id=camera_id or "Not specified",
            time_range="N/A",
            created_at=datetime.now().isoformat(),
            executive_summary=["No evidence clips were included in this report."],
            timeline=[],
            evidence=[],
            recommended_actions=[]
        )
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as mm:ss"""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"
