import os
import cv2
import numpy as np
import onnxruntime as ort
import logging

logger = logging.getLogger(__name__)

class SilentFaceAntiSpoofing:
    """
    ONNX inference wrapper for MiniFASNetV2 / MiniFASNetV1 models.
    Supports dynamic scaling, cropping, and model loading.
    """
    def __init__(self, model_path, input_size=(80, 80)):
        self.model_path = model_path
        self.input_size = input_size
        
        # Parse model parameters from filename
        model_name = os.path.basename(model_path)
        parts = model_name.replace(".onnx", "").split("_")
        
        # Default fallback values
        self.scale = 2.7
        self.model_type = "MiniFASNetV2"
        
        try:
            if len(parts) > 0:
                self.scale = float(parts[0])
            if len(parts) > 1 and "x" in parts[1]:
                h, w = parts[1].split("x")
                self.input_size = (int(h), int(w))
            if len(parts) > 2:
                self.model_type = parts[2]
        except Exception as e:
            logger.warning(f"Error parsing model name {model_name}, using defaults. Error: {e}")
            
        logger.info(f"Initialized liveness model: {model_name} (Scale: {self.scale}, Input size: {self.input_size})")

    def _get_new_box(self, src_w, src_h, bbox, scale):
        """
        Calculates expanded cropped box for anti-spoofing input.
        bbox format: [x, y, w, h]
        """
        x, y, box_w, box_h = bbox
        
        # Ensure scale is within image boundaries
        scale = min((src_h - 1) / max(1, box_h), min((src_w - 1) / max(1, box_w), scale))

        new_width = box_w * scale
        new_height = box_h * scale
        center_x, center_y = box_w / 2.0 + x, box_h / 2.0 + y

        left_top_x = center_x - new_width / 2.0
        left_top_y = center_y - new_height / 2.0
        right_bottom_x = center_x + new_width / 2.0
        right_bottom_y = center_y + new_height / 2.0

        if left_top_x < 0:
            right_bottom_x -= left_top_x
            left_top_x = 0

        if left_top_y < 0:
            right_bottom_y -= left_top_y
            left_top_y = 0

        if right_bottom_x > src_w - 1:
            left_top_x -= (right_bottom_x - src_w + 1)
            right_bottom_x = src_w - 1

        if right_bottom_y > src_h - 1:
            left_top_y -= (right_bottom_y - src_h + 1)
            right_bottom_y = src_h - 1

        return int(left_top_x), int(left_top_y), int(right_bottom_x), int(right_bottom_y)

    def crop(self, org_img, bbox):
        """
        Crops and resizes face image to input size based on bounding box.
        org_img: source frame
        bbox: [x, y, w, h] face bounding box
        """
        src_h, src_w = org_img.shape[:2]
        left_top_x, left_top_y, right_bottom_x, right_bottom_y = self._get_new_box(
            src_w, src_h, bbox, self.scale
        )
        
        crop_img = org_img[left_top_y:right_bottom_y + 1, left_top_x:right_bottom_x + 1]
        if crop_img.size == 0:
            return None
            
        dst_img = cv2.resize(crop_img, self.input_size, interpolation=cv2.INTER_LINEAR)
        return dst_img

    def predict(self, session, cropped_face):
        """
        Runs model prediction on cropped BGR face.
        session: ThreadSafeONNXSession instance
        """
        if cropped_face is None or cropped_face.size == 0:
            return np.zeros((1, 3))
            
        # Transform BGR to tensor format: [H, W, C] -> [C, H, W]
        # Transpose channel order HWC to CHW
        transposed = cropped_face.transpose((2, 0, 1))
        # Add batch dimension and convert to float32
        tensor = np.expand_dims(transposed, axis=0).astype(np.float32)
        
        # Inference
        input_name = session.session.get_inputs()[0].name
        output_name = session.session.get_outputs()[0].name
        
        outputs = session.run([output_name], {input_name: tensor})
        logits = outputs[0]
        
        # Softmax normalization
        exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
        return probs
