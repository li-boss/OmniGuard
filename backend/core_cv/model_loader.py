import os
import logging
import numpy as np
import cv2
import threading
import onnxruntime as ort
from ultralytics import YOLO

class ThreadSafeONNXSession:
    def __init__(self, model_path, use_gpu=False):
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if use_gpu else ['CPUExecutionProvider']
        try:
            self.session = ort.InferenceSession(model_path, providers=providers)
        except Exception:
            self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.lock = threading.Lock()

    def run(self, output_names, input_feed, run_options=None):
        with self.lock:
            return self.session.run(output_names, input_feed, run_options)

logger = logging.getLogger(__name__)

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weights')

class ModelLoader:
    _yolo = None
    _face_detector = None
    _face_recognizer = None
    _face_detector_lock = threading.Lock()
    _yolo_lock = threading.Lock()
    _face_recognizer_lock = threading.Lock()

    @classmethod
    def get_yolo(cls):
        if cls._yolo is None:
            with cls._yolo_lock:
                if cls._yolo is None:
                    path = os.path.join(WEIGHTS_DIR, 'yolov8n.pt')
                    logger.info(f"Loading YOLOv8 model from {path}...")
                    cls._yolo = YOLO(path)
        return cls._yolo

    @classmethod
    def get_face_detector(cls):
        if cls._face_detector is None:
            with cls._face_detector_lock:
                if cls._face_detector is None:
                    logger.info("Loading RetinaFace Detector (mobile0.25)...")
                    from retinaface import RetinaFaceDetector
                    import torch
                    device = 'cuda' if torch.cuda.is_available() else 'cpu'
                    detector = RetinaFaceDetector(model='mobile0.25', device=device)
                    # Preset fixed input shape to avoid constant anchor generation overhead
                    detector.set_input_shape(256, 256)
                    cls._face_detector = detector
        return cls._face_detector

    @classmethod
    def get_face_recognizer(cls):
        if cls._face_recognizer is None:
            with cls._face_recognizer_lock:
                if cls._face_recognizer is None:
                    # Ensure model is downloaded first
                    try:
                        from .scripts.download_models import download_required_models
                        download_required_models()
                    except Exception as de:
                        logger.error(f"Failed to auto-download models: {de}")
                        
                    path = os.path.join(WEIGHTS_DIR, 'arcface_w600k_r50.onnx')
                    logger.info(f"Loading ArcFace Recognizer from {path}...")
                    use_gpu = 'CUDAExecutionProvider' in ort.get_available_providers()
                    cls._face_recognizer = ThreadSafeONNXSession(path, use_gpu=use_gpu)
        return cls._face_recognizer

    @classmethod
    def warmup(cls):
        logger.info("Starting model warmup...")
        # 1. Warmup YOLO
        yolo_path = os.path.join(WEIGHTS_DIR, 'yolov8n.pt')
        if os.path.exists(yolo_path):
            try:
                model = cls.get_yolo()
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                model(dummy, verbose=False)
                logger.info("YOLOv8 warmup completed.")
            except Exception as e:
                logger.error(f"YOLOv8 warmup failed: {e}")
        else:
            logger.warning(f"YOLOv8 weight file not found at {yolo_path}, skipping warmup.")

        # 2. Warmup Face Detector (RetinaFace)
        try:
            detector = cls.get_face_detector()
            dummy_face = np.zeros((256, 256, 3), dtype=np.uint8)
            detector.set_input_shape(256, 256)
            detector.inference(dummy_face)
            logger.info("RetinaFace Detector warmup completed.")
        except Exception as e:
            logger.error(f"RetinaFace Detector warmup failed: {e}")

        # 3. Warmup Face Recognizer (ArcFace)
        recognizer_path = os.path.join(WEIGHTS_DIR, 'arcface_w600k_r50.onnx')
        if not os.path.exists(recognizer_path):
            try:
                from .scripts.download_models import download_required_models
                download_required_models()
            except Exception as de:
                logger.error(f"Failed to auto-download models: {de}")

        if os.path.exists(recognizer_path):
            try:
                net = cls.get_face_recognizer()
                dummy_input = np.zeros((1, 3, 112, 112), dtype=np.float32)
                input_name = net.session.get_inputs()[0].name
                output_name = net.session.get_outputs()[0].name
                net.run([output_name], {input_name: dummy_input})
                logger.info("ArcFace Recognizer warmup completed.")
            except Exception as e:
                logger.error(f"ArcFace Recognizer warmup failed: {e}")
        else:
            logger.warning(f"ArcFace weight file not found at {recognizer_path}, skipping warmup.")
            
        logger.info("All model warmups completed.")

    @classmethod
    def release_all(cls):
        logger.info("Releasing all cached model resources...")
        cls._yolo = None
        cls._face_detector = None
        cls._face_recognizer = None
