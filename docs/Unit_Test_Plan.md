# Unit Test Plan

This is a project-created supporting document, not an official mentor template.

| Test ID | Module | Test Description | Input | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|---|
| UT-001 | Presence tracking | Present, absent, present timeline | 0-10 present, 10-12 absent, 12-30 present | Ratio approximately 0.933333 | Ratio 0.933333 | PASS |
| UT-002 | Presence tracking | Continuous face presence | 10-20 present | Ratio 1.0 | Ratio 1.0 | PASS |
| UT-003 | Presence tracking | Continuous face absence | 10-20 absent | Ratio 0.0 | Ratio 0.0 | PASS |
| UT-004 | Presence tracking | Multiple absence intervals | 0-5 present, 5-7 absent, 7-10 present, 10-13 absent, 13-20 present | Ratio 0.7 | Ratio 0.7 | PASS |
| UT-005 | Presence tracking | Termination closes monitoring | 100-108 present, 108-110 absent | Ratio 0.8 | Ratio 0.8 | PASS |
| UT-006 | Face absence decision | One penalty at configured threshold | Deterministic regression setup | One FACE_ABSENT deduction | Verified by existing regression test | PASS |
| UT-007 | Face absence decision | Termination persists reason and score | Deterministic regression setup | TERMINATED session with reason | Verified by existing regression test | PASS |
| UT-008 | Browser monitoring | Reject foreign session event and deduplicate event ID | Existing regression setup | Ownership enforced and duplicate ignored | Verified by existing regression test | PASS |
| UT-009 | Question loading | Repair empty exam question set | Existing regression setup | Questions available after repair | Verified by existing regression test | PASS |
| UT-010 | Live webcam workflow | Face return through a real browser camera | Live browser and camera | Monitoring interval closes correctly | Not executed in this environment | NOT TESTED |
| UT-011 | LLM reporting | Real provider report generation | API key and provider | Provider response returned | Not executed without API key | NOT TESTED |
