# Smart Campus Security Spec

## Goal

Build a campus security system that combines camera streams, face access control,
perimeter rules, alarm handling, notifications, and dashboard reporting.

## Modules

- Frontend Vue application for dashboards and operations.
- Flask backend for REST APIs, WebSocket events, scheduling, and CV pipeline orchestration.
- Computer vision core for stream parsing, face recognition, YOLO detection, and rule evaluation.
- Ops files for deployment, reverse proxy, RTMP relay, and CI/CD.
