import os
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WEIGHTS_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS = {
    "yolov8n.pt": "https://github.com/ultralytics/assets/releases/download/v8.2.0/yolov8n.pt",
    "face_detection_yunet_2023mar.onnx": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "mobilefacenet.onnx": "https://raw.githubusercontent.com/Eartherai/FaceAuthApp/main/FaceAuthApp/artifacts/mobilefacenet_fp32.onnx"
}

def download_file(url, dest_path):
    logger.info(f"Downloading {url} to {dest_path}...")
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(dest_path, 'wb') as out_file:
            out_file.write(response.read())
        logger.info(f"Successfully downloaded {dest_path}")
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        raise

def main():
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    for filename, url in MODELS.items():
        dest = os.path.join(WEIGHTS_DIR, filename)
        if os.path.exists(dest):
            logger.info(f"{filename} already exists at {dest}, skipping.")
        else:
            download_file(url, dest)

if __name__ == "__main__":
    main()
