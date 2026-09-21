# Database Design

The authoritative database is `database/exam.db`. Initialization is migration-safe and preserves existing records.

Core tables: `users`, `exams`, `questions`, `options`, `exam_sessions`, `exam_submissions`, `exam_answers`, `proctoring_logs`, `security_logs`, `active_sessions`, `suspicious_events`, `integrity_reports`, and `evidence`.

`exam_sessions` belongs to a candidate and exam and stores lifecycle status, identity verification, integrity score, active timing fields, and termination reason. Proctoring logs and evidence reference the session. Submissions reference both candidate and session where available.
