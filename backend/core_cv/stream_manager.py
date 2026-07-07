import cv2


class StreamManager:
    def __init__(self, url, frame_skip=2):
        self.url = url
        self.frame_skip = frame_skip
        self.capture = cv2.VideoCapture(url)
        self.index = 0

    def read(self):
        ok, frame = self.capture.read()
        self.index += 1
        if not ok or self.index % self.frame_skip != 0:
            return None
        return frame

    def release(self):
        self.capture.release()
