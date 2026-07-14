import sys
import unittest
import threading
import time
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core_cv.rule_engine import RuleEngine

class RuleEngineConcurrencyTest(unittest.TestCase):
    def test_concurrent_evaluation_and_cleanup(self):
        rule_engine = RuleEngine()
        exceptions = []
        running = True

        # Mock alert zone
        zone = {
            "id": 1,
            "polygon": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}],
            "stay_seconds": 1
        }

        def worker_eval(worker_id):
            nonlocal running
            obj_id = f"obj_{worker_id}"
            box = [0.1, 0.1, 0.3, 0.3]
            while running:
                try:
                    rule_engine.evaluate_stay(obj_id, box, zone)
                    time.sleep(0.001)
                except Exception as e:
                    exceptions.append(e)
                    break

        def worker_cleanup():
            nonlocal running
            while running:
                try:
                    rule_engine.cleanup_expired_states(timeout_seconds=0.01)
                    time.sleep(0.002)
                except Exception as e:
                    exceptions.append(e)
                    break

        # Spin up evaluation threads and a cleanup thread
        threads = []
        for i in range(10):
            t = threading.Thread(target=worker_eval, args=(i,))
            t.start()
            threads.append(t)

        t_clean = threading.Thread(target=worker_cleanup)
        t_clean.start()
        threads.append(t_clean)

        # Run stress test for 1 second
        time.sleep(1.0)
        running = False

        for t in threads:
            t.join()

        # Verify no exceptions were raised
        self.assertEqual(len(exceptions), 0, f"Exceptions encountered: {exceptions}")

if __name__ == "__main__":
    unittest.main()
