# vision/mock.py
"""
Vision mock for development and CI.
Provides is_ready() and infer(image) to match the real yolo_engine API.
"""

def is_ready():
    # Always ready in mock mode
    return True

def infer(image):
    """
    Accepts an image-like object or path and returns a minimal detection structure.
    Replace with real inference return format if needed.
    """
    # Return an empty detection list for deterministic behavior
    return {"detections": [], "mock": True}
