"""
Twelve Labs API Client Wrapper

Provides a simplified interface for video analysis using Twelve Labs.
"""
import os
import time
from typing import Generator, Optional
from twelvelabs import TwelveLabs


class TwelveLabsClient:
    """Client wrapper for Twelve Labs video analysis API."""
    
    DEFAULT_INDEX_NAME = "surveillance_app_index"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Twelve Labs client.
        
        Args:
            api_key: API key. If not provided, reads from TWELVE_LABS_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("TWELVE_LABS_API_KEY")
        if not self.api_key:
            raise ValueError("Twelve Labs API key required. Set TWELVE_LABS_API_KEY or pass api_key.")
        
        self.client = TwelveLabs(api_key=self.api_key)
        self.index_id = None
        self._ensure_index()
    
    def _ensure_index(self):
        """Create or retrieve the default index."""
        # Check if index already exists
        try:
            indexes = self.client.indexes.list()
            for idx in indexes:
                # SDK uses index_name attribute
                if getattr(idx, 'index_name', None) == self.DEFAULT_INDEX_NAME:
                    self.index_id = idx.id
                    print(f"Using existing index: {self.index_id}")
                    return
        except Exception as e:
            print(f"Error listing indexes: {e}")
        
        # Create new index
        index = self.client.indexes.create(
            index_name=self.DEFAULT_INDEX_NAME,
            models=[{"model_name": "pegasus1.2", "model_options": ["visual", "audio"]}]
        )
        self.index_id = index.id
        print(f"Created new index: {self.index_id}")
    
    def preprocess_video(self, file_path: str, target_fps: int = 5, target_width: int = 640) -> str:
        """Preprocess video for faster upload and indexing.
        
        Reduces framerate and resolution to optimize for Twelve Labs.
        
        Args:
            file_path: Path to original video
            target_fps: Target framerate (default 5fps)
            target_width: Target width in pixels (height scales proportionally)
            
        Returns:
            Path to preprocessed video (temp file)
        """
        import cv2
        import tempfile
        
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return file_path  # Return original if can't open
        
        # Get original properties
        orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30
        orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Calculate new dimensions (maintain aspect ratio)
        scale = target_width / orig_width
        new_width = target_width
        new_height = int(orig_height * scale)
        # Ensure even dimensions for codec compatibility
        new_height = new_height if new_height % 2 == 0 else new_height + 1
        
        # Calculate frame skip (to reduce framerate)
        frame_skip = max(1, int(orig_fps / target_fps))
        
        # Create temp output file
        fd, output_path = tempfile.mkstemp(suffix='.mp4')
        import os
        os.close(fd)
        
        writer = cv2.VideoWriter(
            output_path,
            cv2.VideoWriter_fourcc(*'mp4v'),
            target_fps,
            (new_width, new_height)
        )
        
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only keep every Nth frame
            if frame_count % frame_skip == 0:
                resized = cv2.resize(frame, (new_width, new_height))
                writer.write(resized)
            
            frame_count += 1
        
        cap.release()
        writer.release()
        
        # Log file size comparison
        import os
        orig_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        new_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        reduction = (1 - new_size / orig_size) * 100 if orig_size > 0 else 0
        
        print(f"[Preprocess] {orig_fps:.0f}fps → {target_fps}fps, {orig_width}x{orig_height} → {new_width}x{new_height}")
        print(f"[Preprocess] File size: {orig_size:.1f}MB → {new_size:.1f}MB ({reduction:.0f}% smaller)")
        
        return output_path
    
    def upload_and_index_video(self, file_path: str, callback=None, preprocess: bool = True) -> str:
        """Upload a video file and index it.
        
        Args:
            file_path: Path to the video file
            callback: Optional callback(status: str) for progress updates
            preprocess: If True, reduce framerate/resolution before upload (default True)
            
        Returns:
            indexed_asset_id: The ID of the indexed asset
        """
        import os
        
        # Preprocess video for faster upload/indexing
        preprocessed_path = None
        if preprocess:
            if callback:
                callback("Optimizing video (reducing framerate)...")
            preprocessed_path = self.preprocess_video(file_path)
            upload_path = preprocessed_path
        else:
            upload_path = file_path
        
        if callback:
            callback("Uploading video...")
        
        # Upload the file
        with open(upload_path, "rb") as f:
            asset = self.client.assets.create(
                method="direct",
                file=f
            )
        
        # Clean up preprocessed temp file
        if preprocessed_path and preprocessed_path != file_path:
            try:
                os.remove(preprocessed_path)
            except:
                pass
        
        if callback:
            callback(f"Upload complete. Indexing...")
        
        # Index the asset
        indexed_asset = self.client.indexes.indexed_assets.create(
            index_id=self.index_id,
            asset_id=asset.id
        )
        
        # Wait for indexing to complete
        while True:
            indexed_asset = self.client.indexes.indexed_assets.retrieve(
                index_id=self.index_id,
                indexed_asset_id=indexed_asset.id
            )
            
            if callback:
                callback(f"Indexing: {indexed_asset.status}")
            
            if indexed_asset.status == "ready":
                break
            elif indexed_asset.status == "failed":
                raise RuntimeError("Video indexing failed")
            
            time.sleep(3)
        
        if callback:
            callback("Ready for analysis!")
        
        return indexed_asset.id
    
    def analyze(self, indexed_asset_id: str, prompt: str) -> Generator[str, None, None]:
        """Analyze a video with a natural language prompt.
        
        Args:
            indexed_asset_id: The ID of the indexed video
            prompt: The analysis prompt
            
        Yields:
            Text chunks from the streaming response
        """
        text_stream = self.client.analyze_stream(
            video_id=indexed_asset_id,
            prompt=prompt
        )
        
        for text in text_stream:
            if text.event_type == "text_generation":
                yield text.text
    
    def analyze_sync(self, indexed_asset_id: str, prompt: str) -> str:
        """Analyze a video and return complete response (non-streaming).
        
        Args:
            indexed_asset_id: The ID of the indexed video
            prompt: The analysis prompt
            
        Returns:
            Complete analysis text
        """
        result = []
        for chunk in self.analyze(indexed_asset_id, prompt):
            result.append(chunk)
        return "".join(result)
    
    def analyze_video(self, file_path: str, prompt: str) -> str:
        """Upload a video file and analyze it with a prompt (convenience method).
        
        Args:
            file_path: Path to the video file
            prompt: The analysis prompt
            
        Returns:
            Analysis text result
        """
        # Upload and index
        indexed_asset_id = self.upload_and_index_video(file_path)
        
        # Analyze
        return self.analyze_sync(indexed_asset_id, prompt)
    
    def search_moments(self, query: str, top_k: int = 5) -> list:
        """Search for moments in indexed videos matching a query.
        
        Note: Since the index uses Pegasus (not Marengo), we use analyze
        to find relevant moments instead of the search API.
        
        Args:
            query: Natural language search query
            top_k: Maximum number of results to return
            
        Returns:
            List of dicts with start, end, confidence, video_id, query
        """
        try:
            # Get the most recent indexed asset
            assets = self.get_indexed_assets()
            if not assets:
                print("No indexed assets found")
                return []
            
            # Use the first/most recent asset
            asset = assets[0]
            asset_id = getattr(asset, 'id', None)
            if not asset_id:
                print("Could not get asset ID")
                return []
            
            # Use analyze to find moments matching the query
            prompt = f"""Analyze this entire video carefully and find ALL moments where: {query}

IMPORTANT: List EVERY occurrence, even if the same event happens multiple times. Do not summarize or combine repeated events.

For EACH moment found, provide:
- Start time in seconds
- End time in seconds  
- Brief description (5 words max)
- Confidence (high/medium/low)

Format each finding on its own line as: [START_SEC]-[END_SEC]: [DESCRIPTION] ([CONFIDENCE])
Example: 15-22: Person near door (high)

If no relevant moments found, respond with "NONE"."""

            result = self.analyze_sync(asset_id, prompt)
            
            # Parse the response to extract moments
            moments = self._parse_analysis_moments(result, query, asset_id)
            return moments[:top_k]
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def _parse_analysis_moments(self, analysis_text: str, query: str, video_id: str) -> list:
        """Parse analysis response to extract moment timestamps."""
        moments = []
        
        if not analysis_text or "NONE" in analysis_text.upper():
            return moments
        
        import re
        
        def parse_time(time_str: str) -> float:
            """Convert time string to seconds. Handles mm:ss, m:ss, or plain seconds."""
            time_str = time_str.strip()
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 2:
                    mins = float(parts[0])
                    secs = float(parts[1])
                    return mins * 60 + secs
                elif len(parts) == 3:  # h:mm:ss
                    hours = float(parts[0])
                    mins = float(parts[1])
                    secs = float(parts[2])
                    return hours * 3600 + mins * 60 + secs
            return float(time_str)
        
        # Pattern 1: seconds format: 120-150: description (confidence)
        pattern_seconds = r'(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*:\s*([^(]+)\s*\((\w+)\)'
        
        # Pattern 2: mm:ss format: 2:00-2:30: description (confidence)
        pattern_mmss = r'(\d+:\d{2})\s*[-–]\s*(\d+:\d{2})\s*:\s*([^(]+)\s*\((\w+)\)'
        
        # Try mm:ss pattern first (more specific)
        matches = re.findall(pattern_mmss, analysis_text)
        if not matches:
            matches = re.findall(pattern_seconds, analysis_text)
        
        for match in matches:
            try:
                start = parse_time(match[0])
                end = parse_time(match[1])
                label = match[2].strip()
                conf_str = match[3].lower()
                
                confidence = {"high": 0.9, "medium": 0.7, "low": 0.5}.get(conf_str, 0.6)
                
                moments.append({
                    'start': start,
                    'end': end,
                    'confidence': confidence,
                    'video_id': video_id,
                    'query': query,
                    'label': label
                })
            except (ValueError, IndexError):
                continue
        
        # If no structured matches, try to extract any time ranges mentioned
        if not moments and len(analysis_text) > 20 and "NONE" not in analysis_text.upper():
            # Try to find any time-like patterns in the text
            time_pattern = r'(\d+:\d{2}|\d+(?:\.\d+)?\s*(?:s|sec|seconds)?)'
            times = re.findall(time_pattern, analysis_text)
            if len(times) >= 2:
                try:
                    start = parse_time(times[0].replace('s', '').replace('sec', '').replace('seconds', '').strip())
                    end = parse_time(times[1].replace('s', '').replace('sec', '').replace('seconds', '').strip())
                    moments.append({
                        'start': start,
                        'end': end,
                        'confidence': 0.5,
                        'video_id': video_id,
                        'query': query,
                        'label': analysis_text[:80].strip()
                    })
                except ValueError:
                    pass
            
            # Last resort: generic moment
            if not moments:
                moments.append({
                    'start': 0,
                    'end': 10,
                    'confidence': 0.5,
                    'video_id': video_id,
                    'query': query,
                    'label': analysis_text[:50].strip()
                })
        
        return moments
    
    def search_multiple_queries(self, queries: list, top_k_per_query: int = 3) -> list:
        """Search with multiple queries and combine results.
        
        Args:
            queries: List of search query strings
            top_k_per_query: Max results per query
            
        Returns:
            Combined list of moments from all queries
        """
        all_moments = []
        for query in queries:
            moments = self.search_moments(query, top_k=top_k_per_query)
            all_moments.extend(moments)
        return all_moments
    
    def label_clip(self, indexed_asset_id: str, start: float, end: float) -> str:
        """Generate a short label for a video clip.
        
        Args:
            indexed_asset_id: The ID of the indexed video
            start: Start time in seconds
            end: End time in seconds
            
        Returns:
            Short descriptive label (3-7 words)
        """
        try:
            prompt = f"In 5 words or less, describe what happens between {start:.1f}s and {end:.1f}s."
            result = self.analyze_sync(indexed_asset_id, prompt)
            # Truncate to first sentence/7 words
            words = result.split()[:7]
            return ' '.join(words)
        except Exception as e:
            print(f"Label generation error: {e}")
            return "Activity detected"
    
    def get_indexed_assets(self) -> list:
        """Get list of all indexed assets.
        
        Returns:
            List of indexed asset objects
        """
        try:
            assets = self.client.indexes.indexed_assets.list(index_id=self.index_id)
            return list(assets)
        except Exception as e:
            print(f"Error listing assets: {e}")
            return []

