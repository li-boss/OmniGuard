import sys
import unittest
import time
import numpy as np
from unittest.mock import MagicMock
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core_cv.pipeline import PipelineInferenceWorker

class PipelineMultiWorkerTest(unittest.TestCase):
    def test_worker_isolation_and_backpressure(self):
        # Create a mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.camera_id = "test-cam"
        
        processed_frames = []
        def slow_inference(frame):
            processed_frames.append(frame[0, 0, 0]) # save unique pixel val of frame
            time.sleep(0.1) # Simulate slow AI processing
            return []
            
        mock_pipeline.run_inference = slow_inference
        
        # Instantiate worker
        worker = PipelineInferenceWorker(mock_pipeline)
        worker.start()
        
        try:
            # 1. Submit first frame (pixel val = 1)
            frame_1 = np.ones((10, 10, 3), dtype=np.uint8) * 1
            worker.submit(frame_1)
            
            # Wait a tiny bit for the worker to start processing frame_1
            time.sleep(0.02)
            
            # 2. While worker is busy, submit frame_2 (pixel val = 2) and frame_3 (pixel val = 3)
            frame_2 = np.ones((10, 10, 3), dtype=np.uint8) * 2
            frame_3 = np.ones((10, 10, 3), dtype=np.uint8) * 3
            
            worker.submit(frame_2)
            worker.submit(frame_3) # Should overwrite frame_2 in the single-slot buffer
            
            # Wait for worker to finish processing everything
            time.sleep(0.3)
            
            # Assertions:
            # - First frame processed should be frame_1 (val = 1)
            # - Next frame processed should be frame_3 (val = 3) because frame_2 was overwritten (backpressure drop-oldest)
            self.assertEqual(len(processed_frames), 2)
            self.assertEqual(processed_frames[0], 1)
            self.assertEqual(processed_frames[1], 3)
            
        finally:
            worker.stop()

if __name__ == "__main__":
    unittest.main()
