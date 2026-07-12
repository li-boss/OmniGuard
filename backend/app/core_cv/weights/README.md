# Fire and smoke detection model

The runtime expects `fire_smoke_yolov8n.onnx` in this directory. It is a YOLOv8n model with
`fire` and `smoke` classes and a 640 x 640 input. The binary is ignored by Git.

Source: [luminous0219/fire-and-smoke-detection-yolov8](https://github.com/luminous0219/fire-and-smoke-detection-yolov8),
`weights/best.pt`, trained for 150 epochs. The source repository and model use AGPL-3.0.

To reproduce the ONNX export, first install the export-only tools, then run the script:

```powershell
python -m pip install ultralytics onnx onnxslim
powershell -ExecutionPolicy Bypass -File backend/scripts/download_fire_model.ps1
```

The application itself uses OpenCV DNN and does not require those export-only packages.
