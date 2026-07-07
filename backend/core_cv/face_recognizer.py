import numpy as np


class FaceRecognizer:
    def __init__(self, threshold=0.45):
        self.threshold = threshold

    def compare(self, known_feature, candidate_feature):
        distance = np.linalg.norm(np.asarray(known_feature) - np.asarray(candidate_feature))
        return {"matched": distance <= self.threshold, "distance": float(distance)}

    def extract_feature(self, image):
        raise NotImplementedError("Connect dlib or another face feature extractor here.")
