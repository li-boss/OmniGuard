class StreamManager:
    def __init__(self):
        self.streams = {}

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
