import argparse
import json
import sys
from pathlib import Path

import numpy as np


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from flask import Flask
from services.audio_event_detector import get_audio_event_detector


def load_wav_16k_mono(path):
    try:
        from scipy.io import wavfile
        from scipy.signal import resample_poly
    except ImportError as exc:
        raise RuntimeError("缺少 scipy，请安装 backend/requirements-audio.txt") from exc

    sample_rate, waveform = wavfile.read(path)
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    if np.issubdtype(waveform.dtype, np.integer):
        limit = max(abs(np.iinfo(waveform.dtype).min), np.iinfo(waveform.dtype).max)
        waveform = waveform.astype(np.float32) / float(limit)
    else:
        waveform = waveform.astype(np.float32)
    waveform = np.clip(waveform, -1.0, 1.0)
    if sample_rate != 16000:
        from math import gcd

        divisor = gcd(int(sample_rate), 16000)
        waveform = resample_poly(waveform, 16000 // divisor, int(sample_rate) // divisor)
    return np.asarray(waveform, dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description="使用 YAMNet 离线测试 WAV 环境声音")
    parser.add_argument("wav_file", help="待测试 WAV 文件")
    parser.add_argument("--save-embedding", help="可选：保存 YAMNet 1024维 embedding 为 .npy")
    args = parser.parse_args()

    wav_path = Path(args.wav_file)
    if not wav_path.is_file():
        raise SystemExit(f"WAV 文件不存在：{wav_path}")

    waveform = load_wav_16k_mono(wav_path)
    app = Flask("audio_wav_test", root_path=str(BACKEND_DIR))
    detector = get_audio_event_detector(app)
    result = detector.analyze_waveform(waveform)
    result.pop("embedding")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.save_embedding:
        embedding = detector.extract_embeddings(waveform)
        output_path = Path(args.save_embedding)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(output_path, embedding)
        print(f"embedding 已保存：{output_path}，shape={embedding.shape}")


if __name__ == "__main__":
    main()
