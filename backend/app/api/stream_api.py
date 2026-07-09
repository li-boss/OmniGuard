from datetime import datetime

from flask import Blueprint, Response


stream_bp = Blueprint("streams", __name__)


@stream_bp.get("/demo.mjpg")
def demo_stream():
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
      <rect width="960" height="540" fill="#111820"/>
      <rect x="34" y="34" width="892" height="472" fill="none" stroke="#3b5163" stroke-width="3"/>
      <text x="64" y="160" fill="#edf5f7" font-family="Arial, sans-serif" font-size="42" font-weight="700">Smart Campus Video</text>
      <text x="64" y="224" fill="#a7bac8" font-family="Arial, sans-serif" font-size="26">Demo stream placeholder</text>
      <text x="64" y="286" fill="#68d19d" font-family="Arial, sans-serif" font-size="24">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</text>
      <circle cx="820" cy="138" r="12" fill="#d94841"/>
      <text x="842" y="147" fill="#f8d8d6" font-family="Arial, sans-serif" font-size="22">LIVE</text>
    </svg>
    """
    return Response(svg.strip(), mimetype="image/svg+xml")
