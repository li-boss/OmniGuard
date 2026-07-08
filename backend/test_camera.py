import os
import sys
import cv2
import numpy as np

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core_cv.model_loader import ModelLoader

def main():
    print("Initializing models and warming up...")
    try:
        # Load YOLO and Face Detector
        yolo_model = ModelLoader.get_yolo()
        face_detector = ModelLoader.get_face_detector()
    except Exception as e:
        print(f"Error loading models: {e}")
        print("Please run 'python core_cv/weights/download_weights.py' to download weights first.")
        return
    
    # Try to open webcam
    camera_index = 0
    print(f"Opening webcam (index {camera_index})... Press 'q' to quit.")
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"\nError: Could not open webcam with index {camera_index}.")
        print("Possible causes:")
        print("1. No camera/webcam is connected to this system.")
        print("2. The camera is currently being used by another application (Zoom, Teams, WeChat, etc.).")
        print("3. Driver permissions are blocking OpenCV access.")
        print("\nNote: You can still run E2E/mock tests even if you don't have a webcam.")
        return
        
    cv2.namedWindow("Smart Campus Security - Live CV Test", cv2.WINDOW_NORMAL)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame from camera.")
            break
            
        fh, fw = frame.shape[:2]
        
        # 1. Run YOLOv8 detection
        results = yolo_model(frame, verbose=False)
        boxes = results[0].boxes
        
        for box in boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            # YOLO COCO class 0 is 'person'
            if cls_id == 0 and conf > 0.4:
                # Get absolute box coords
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"Person {conf:.2f}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                # 2. Run Face Detection on the person region
                px1 = max(0, x1)
                py1 = max(0, y1)
                px2 = min(fw, x2)
                py2 = min(fh, y2)
                
                if px2 > px1 and py2 > py1:
                    person_crop = frame[py1:py2, px1:px2]
                    pch, pcw = person_crop.shape[:2]
                    if pch >= 20 and pcw >= 20:
                        face_detector.setInputSize((pcw, pch))
                        retval, faces = face_detector.detect(person_crop)
                        if faces is not None and len(faces) > 0:
                            for face in faces:
                                if not np.isfinite(face[0:4]).all():
                                    continue
                                fx, fy, fw_f, fh_f = map(int, face[0:4])
                                # Map relative to whole frame coordinates
                                abs_fx1 = px1 + fx
                                abs_fy1 = py1 + fy
                                abs_fx2 = px1 + fx + fw_f
                                abs_fy2 = py1 + fy + fh_f
                                
                                cv2.rectangle(frame, (abs_fx1, abs_fy1), (abs_fx2, abs_fy2), (255, 0, 0), 2)
                                cv2.putText(frame, "Face", (abs_fx1, abs_fy1 - 5),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)

        cv2.imshow("Smart Campus Security - Live CV Test", frame)
        
        # Press q to exit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
    print("Camera test completed.")

if __name__ == "__main__":
    main()
