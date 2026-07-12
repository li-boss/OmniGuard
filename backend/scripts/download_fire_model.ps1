$ErrorActionPreference = "Stop"

$url = "https://raw.githubusercontent.com/luminous0219/fire-and-smoke-detection-yolov8/main/weights/best.pt"
$weightsDir = Join-Path $PSScriptRoot "..\app\core_cv\weights"
$destination = Join-Path $weightsDir "fire_smoke_yolov8n.onnx"
$temporaryPt = Join-Path $env:TEMP "fire_smoke_yolov8n.pt"
$expectedPtSha256 = "ac0a10257b2bc1f20c9d957f8adeeb61dd6140322fc19d0b4a116cb491776d16"

New-Item -ItemType Directory -Force $weightsDir | Out-Null
Invoke-WebRequest -Uri $url -OutFile $temporaryPt
$actualSha256 = (Get-FileHash -Algorithm SHA256 $temporaryPt).Hash.ToLowerInvariant()
if ($actualSha256 -ne $expectedPtSha256) {
    Remove-Item -LiteralPath $temporaryPt
    throw "Downloaded model checksum mismatch: $actualSha256"
}

$env:FIRE_SMOKE_SOURCE_MODEL = $temporaryPt
$env:FIRE_SMOKE_ONNX_MODEL = $destination
try {
    @'
import os
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError as exc:
    raise SystemExit("Export requires: python -m pip install ultralytics onnx onnxslim") from exc

source = Path(os.environ["FIRE_SMOKE_SOURCE_MODEL"])
destination = Path(os.environ["FIRE_SMOKE_ONNX_MODEL"])
exported = Path(YOLO(source).export(format="onnx", imgsz=640, opset=12, simplify=True, dynamic=False))
exported.replace(destination)
'@ | python -
} finally {
    Remove-Item -LiteralPath $temporaryPt -ErrorAction SilentlyContinue
    Remove-Item Env:FIRE_SMOKE_SOURCE_MODEL -ErrorAction SilentlyContinue
    Remove-Item Env:FIRE_SMOKE_ONNX_MODEL -ErrorAction SilentlyContinue
}
Write-Output "Fire and smoke model exported to $destination"
