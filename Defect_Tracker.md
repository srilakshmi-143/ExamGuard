# Defect Tracker

This is a project-created supporting document, not an official mentor template.

| ID | Module | Defect | Severity | Status | Resolution | Verification |
|---|---|---|---|---|---|---|
| D-001 | Face monitoring | Face absence interval state needed a persisted timestamp-derived presence ratio. | High | Resolved | Added `presence_tracker`, session persistence, and finalization on submission or termination. | Automated presence-ratio tests passed. |
| D-002 | Optional dependencies | Installing optional YOLO dependencies with normal resolution could replace the pinned OpenCV stack. | Medium | Resolved | Documented `--no-deps` installation after mandatory requirements. | `pip check`, Haar load, and YOLO load passed. |
| D-003 | Live browser workflow | A real webcam/browser end-to-end workflow was not available in the execution environment. | Medium | Open | Documented as a verification limitation. | Not executed. |
| D-004 | Screenshots | No live-session screenshots were available for validation. | Low | Open | Documented as not verified; no screenshots were fabricated. | Not executed. |
