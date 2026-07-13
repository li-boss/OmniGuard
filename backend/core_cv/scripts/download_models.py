import os
import sys
import urllib.request
import logging

logger = logging.getLogger(__name__)

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'weights')
os.makedirs(WEIGHTS_DIR, exist_ok=True)

MODELS = {
    "arcface_w600k_r50.onnx": [
        "https://hf-mirror.com/public-data/insightface/resolve/main/models/buffalo_l/w600k_r50.onnx",
        "https://huggingface.co/public-data/insightface/resolve/main/models/buffalo_l/w600k_r50.onnx"
    ],
    "2.7_80x80_MiniFASNetV2.onnx": [
        "https://raw.githubusercontent.com/QingHeYang/Silent-Face-Anti-Spoofing-onnx/main/onnx/2.7_80x80_MiniFASNetV2.onnx",
        "https://ghproxy.cn/https://raw.githubusercontent.com/QingHeYang/Silent-Face-Anti-Spoofing-onnx/main/onnx/2.7_80x80_MiniFASNetV2.onnx"
    ]
}

def download_required_models():
    for name, urls in MODELS.items():
        path = os.path.join(WEIGHTS_DIR, name)
        if os.path.exists(path) and os.path.getsize(path) > 100 * 1024:
            # Model exists and size is reasonable (>100KB)
            logger.info(f"Model file {name} already exists and is valid.")
            continue

        success = False
        for url in urls:
            logger.info(f"Downloading {name} from {url} ...")
            print(f"Downloading {name} from {url} ...", flush=True)
            try:
                # Custom User-Agent to avoid HTTP 403 on some mirrors
                req = urllib.request.Request(
                    url, 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                )
                with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                    meta = response.info()
                    file_size = int(meta.get("Content-Length", 0))
                    print(f"File size: {file_size / (1024 * 1024):.2f} MB", flush=True)

                    block_sz = 8192
                    downloaded = 0
                    while True:
                        buffer = response.read(block_sz)
                        if not buffer:
                            break
                        downloaded += len(buffer)
                        out_file.write(buffer)
                        
                        # Print progress
                        if file_size > 0:
                            percent = downloaded * 100.0 / file_size
                            status = f"\r[{percent:3.1f}%] {downloaded / (1024*1024):.2f}/{file_size / (1024*1024):.2f} MB"
                            sys.stdout.write(status)
                            sys.stdout.flush()

                print(f"\nSuccessfully downloaded {name}", flush=True)
                logger.info(f"Successfully downloaded {name}")
                success = True
                break
            except Exception as e:
                logger.warning(f"Failed to download from {url}: {e}")
                print(f"\nFailed to download from {url}: {e}", flush=True)
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

        if not success:
            raise RuntimeError(f"Could not download required model {name} from any mirrors.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    download_required_models()
