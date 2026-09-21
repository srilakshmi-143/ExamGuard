# Testing

Validated checks include Python compilation, database initialization, template rendering, public/protected route smoke tests, candidate ownership checks, event thresholds, K-Means sparse-data handling, and authorized export access.

Manual browser checks should cover webcam permission, identity verification, fullscreen exit, tab switching, temporary network loss, answer recovery, timeout submission, completed results, terminated retry, and responsive layouts.

Phone detection uses the project-relative YOLO weight at `models/yolo11n.pt`. Test with a real phone image or live webcam: three consecutive detections must confirm one event, create one evidence image, and apply one penalty. Missing dependency/model must report `Phone detection model unavailable` without creating a phone event.
