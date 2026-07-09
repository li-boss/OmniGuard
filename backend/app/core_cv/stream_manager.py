class StreamManager:
    def __init__(self, stream_url=None, frame_skip=1):
        self.streams = {}
        self.stream_url = stream_url
        self.frame_skip = frame_skip
        self._latest_frame = None

    def start(self, camera_id, stream_url):
        self.streams[str(camera_id)] = {
            "cameraId": str(camera_id),
            "streamUrl": stream_url,
            "status": "running",
        }
        return self.streams[str(camera_id)]

    def stop(self, camera_id):
        stream = self.streams.get(str(camera_id))
        if stream:
            stream["status"] = "stopped"
        return stream

    def status(self, camera_id=None):
        if camera_id is None:
            return list(self.streams.values())
        return self.streams.get(str(camera_id), {"cameraId": str(camera_id), "status": "idle"})

    def connect(self):
        return True

    def set_latest_frame(self, frame):
        self._latest_frame = frame

    def get_latest_frame(self):
        return self._latest_frame

    def release(self):
        self._latest_frame = None
