import os
import logging
import numpy as np
import cv2
from ultralytics import YOLO

logger = logging.getLogger(__name__)

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'weights')

class ModelLoader:
    _yolo = None
    _face_detector = None
    _face_recognizer = None

    @classmethod
    def get_yolo(cls):
        if cls._yolo is None:
            path = os.path.join(WEIGHTS_DIR, 'yolov8n.pt')
            logger.info(f"Loading YOLOv8 model from {path}...")
            cls._yolo = YOLO(path)
        return cls._yolo

    @classmethod
    def get_face_detector(cls):
        if cls._face_detector is None:
            path = os.path.join(WEIGHTS_DIR, 'face_detection_yunet_2023mar.onnx')
            logger.info(f"Loading YuNet Face Detector from {path}...")
            # Default input size is 320x320, we can adjust this dynamically using setInputSize()
            cls._face_detector = cv2.FaceDetectorYN.create(
                model=path,
                config="",
                input_size=(320, 320),
                score_threshold=0.6,
                nms_threshold=0.3,
                backend_id=cv2.dnn.DNN_BACKEND_DEFAULT,
                target_id=cv2.dnn.DNN_TARGET_CPU
            )
        return cls._face_detector

    @classmethod
    def get_face_recognizer(cls):
        if cls._face_recognizer is None:
            path = os.path.join(WEIGHTS_DIR, 'mobilefacenet.onnx')
            logger.info(f"Loading MobileFaceNet Face Recognizer from {path}...")
            cls._face_recognizer = cv2.dnn.readNetFromONNX(path)
            cls._face_recognizer.setPreferableBackend(cv2.dnn.DNN_BACKEND_DEFAULT)
            cls._face_recognizer.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
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

        # 2. Warmup Face Detector (YuNet)
        detector_path = os.path.join(WEIGHTS_DIR, 'face_detection_yunet_2023mar.onnx')
        if os.path.exists(detector_path):
            try:
                detector = cls.get_face_detector()
                dummy_face = np.zeros((320, 320, 3), dtype=np.uint8)
                detector.setInputSize((320, 320))
                detector.detect(dummy_face)
                logger.info("YuNet Face Detector warmup completed.")
            except Exception as e:
                logger.error(f"YuNet Face Detector warmup failed: {e}")
        else:
            logger.warning(f"YuNet weight file not found at {detector_path}, skipping warmup.")

        # 3. Warmup Face Recognizer (MobileFaceNet)
        recognizer_path = os.path.join(WEIGHTS_DIR, 'mobilefacenet.onnx')
        if os.path.exists(recognizer_path):
            try:
                net = cls.get_face_recognizer()
                # MobileFaceNet input is 112x112 RGB
                blob = cv2.dnn.blobFromImage(
                    np.zeros((112, 112, 3), dtype=np.uint8),
                    scalefactor=1.0/128.0,
                    size=(112, 112),
                    mean=(127.5, 127.5, 127.5),
                    swapRB=True
                )
                net.setInput(blob)
                net.forward()
                logger.info("MobileFaceNet warmup completed.")
            except Exception as e:
                logger.error(f"MobileFaceNet warmup failed: {e}")
        else:
            logger.warning(f"MobileFaceNet weight file not found at {recognizer_path}, skipping warmup.")
            
        logger.info("All model warmups completed.")

    @classmethod
    def release_all(cls):
        logger.info("Releasing all cached model resources...")
        cls._yolo = None
        cls._face_detector = None
        cls._face_recognizer = None
