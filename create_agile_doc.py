import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Create workbook
wb = openpyxl.Workbook()

# Setup sheets
ws_pb = wb.active
ws_pb.title = "Product Backlog"
ws_sb = wb.create_sheet("Sprint Backlog")
ws_su = wb.create_sheet("Stand up Meeting")
ws_re = wb.create_sheet("Retrospection")

# Styling definitions
header_fill = PatternFill(start_color="F7B787", end_color="F7B787", fill_type="solid") # Matches template orange accent
header_font = Font(name="Calibri", size=11, bold=True)
data_font = Font(name="Calibri", size=10)
thin_border = Border(
    left=Side(style='thin', color='D9D9D9'),
    right=Side(style='thin', color='D9D9D9'),
    top=Side(style='thin', color='D9D9D9'),
    bottom=Side(style='thin', color='D9D9D9')
)

# ---------------------------------------------------------
# 1. PRODUCT BACKLOG
# ---------------------------------------------------------
pb_headers = ["Planned Sprint", "Actual Sprint", "US ID", "User Story Description", "MOSCOW", "Dependency", "Assignee", "Status"]
ws_pb.append(pb_headers)

pb_data = [
    ["1", "1", "US-001", "Set up Flask application architecture, modular blueprint routing, and SQLite database schema.", "MUST HAVE", "No Dependency", "Development Team", "3- Completed"],
    ["1", "1", "US-002", "Implement candidate registration, authentication, and secure password hashing.", "MUST HAVE", "US-001", "Development Team", "3- Completed"],
    ["1", "1", "US-003", "Build candidate photograph capture module during registration for baseline avatar profile setup.", "MUST HAVE", "US-002", "Development Team", "3- Completed"],
    ["1", "1", "US-004", "Develop examination lifecycle and session management routines for starting, saving, and ending tests.", "MUST HAVE", "US-001", "Development Team", "3- Completed"],
    ["1", "1", "US-005", "Implement synthetic data generation using Faker to populate test sessions for framework validation.", "SHOULD HAVE", "US-004", "Development Team", "3- Completed"],
    
    ["2", "2", "US-006", "Integrate OpenCV Haar Cascade classifier for continuous face presence monitoring during exam sessions.", "MUST HAVE", "US-004", "Development Team", "3- Completed"],
    ["2", "2", "US-007", "Implement face absence interval tracking to record exact timestamps and durations of unmonitored sessions.", "MUST HAVE", "US-006", "Development Team", "3- Completed"],
    ["2", "2", "US-008", "Calculate dynamic face presence ratio metric throughout active candidate exam sessions.", "MUST HAVE", "US-007", "Development Team", "3- Completed"],
    ["2", "2", "US-009", "Develop client-side JavaScript logging for browser activity, focus loss, tab switching, and fullscreen exit events.", "MUST HAVE", "US-004", "Development Team", "3- Completed"],
    ["2", "2", "US-010", "Implement rule-based suspicious event detection engine with configurable event thresholds.", "MUST HAVE", "US-007, US-009", "Development Team", "3- Completed"],
    
    ["3", "3", "US-011", "Implement rule-based integrity score calculation engine with weighted suspicious event deductions.", "MUST HAVE", "US-010", "Development Team", "3- Completed"],
    ["3", "3", "US-012", "Develop integrity risk classification module categorizing sessions into Low, Medium, and High risk profiles.", "MUST HAVE", "US-011", "Development Team", "3- Completed"],
    ["3", "3", "US-013", "Integrate LangChain and LLM framework to generate natural-language integrity summaries based on session evidence.", "MUST HAVE", "US-012", "Development Team", "3- Completed"],
    ["3", "3", "US-014", "Build evidence and alert management pipeline for structured storage of violation logs.", "MUST HAVE", "US-010", "Development Team", "3- Completed"],
    ["3", "3", "US-015", "Implement Pandas data analytics for calculating aggregate exam statistics, average integrity, and completion rates.", "MUST HAVE", "US-014", "Development Team", "3- Completed"],
    ["3", "3", "US-016", "Develop statistical visualization pipelines using Matplotlib and Seaborn for session violation distributions.", "SHOULD HAVE", "US-015", "Development Team", "3- Completed"],
    ["3", "3", "US-017", "Implement Scikit-learn K-Means clustering algorithm to perform session and risk profiling across historical attempts.", "SHOULD HAVE", "US-015", "Development Team", "3- Completed"],
    
    ["4", "4", "US-018", "Develop Streamlit administrative and invigilator dashboard for interactive live monitoring and session analysis.", "MUST HAVE", "US-015", "Development Team", "3- Completed"],
    ["4", "4", "US-019", "Implement report export functionalities supporting structured JSON and CSV downloads for invigilator review.", "MUST HAVE", "US-018", "Development Team", "3- Completed"],
    ["4", "4", "US-020", "Perform end-to-end integration testing, browser compatibility validation, and automated regression suite execution.", "MUST HAVE", "US-018", "Development Team", "3- Completed"],
    ["4", "4", "US-021", "Prepare comprehensive technical project documentation, API references, and clean GitHub repository layout.", "MUST HAVE", "US-020", "Development Team", "3- Completed"]
]

for row in pb_data:
    ws_pb.append(row)

# ---------------------------------------------------------
# 2. SPRINT BACKLOG
# ---------------------------------------------------------
sb_headers = ["Sprint", "Task ID", "US ID", "Task Description", "Dependency", "Priority", "Assignee", "Status", "Deliverable"]
ws_sb.append(sb_headers)

sb_data = [
    # Sprint 1
    ["Sprint 1", "TSK-101", "US-001", "Configure Flask environment, register blueprints, and setup SQLite ORM connection.", "None", "High", "Development Team", "3- Completed", "Flask App Blueprint & SQLite DB"],
    ["Sprint 1", "TSK-102", "US-002", "Create Candidate model schema, signup/login routes, and Werkzeug password hashing.", "TSK-101", "High", "Development Team", "3- Completed", "Auth Routes & User Models"],
    ["Sprint 1", "TSK-103", "US-003", "Implement HTML5 video stream JS canvas snippet for candidate registration photo capture.", "TSK-102", "Medium", "Development Team", "3- Completed", "Registration Photo Capture View"],
    ["Sprint 1", "TSK-104", "US-004", "Build database tables and endpoints for Exam and ExamAssignment lifecycle state management.", "TSK-101", "High", "Development Team", "3- Completed", "Exam Lifecycle Endpoints"],
    ["Sprint 1", "TSK-105", "US-005", "Write Python Faker script to populate database with synthetic student attempts and mock metrics.", "TSK-104", "Low", "Development Team", "3- Completed", "Synthetic Data Generator Script"],

    # Sprint 2
    ["Sprint 2", "TSK-201", "US-006", "Integrate OpenCV Haar CascadeXml classifier for real-time video frame face detection.", "TSK-104", "High", "Development Team", "3- Completed", "OpenCV Face Presence Pipeline"],
    ["Sprint 2", "TSK-202", "US-007", "Build backend logic to track continuous face absence start/end timestamps and calculate total duration.", "TSK-201", "High", "Development Team", "3- Completed", "Face Absence Interval Tracker"],
    ["Sprint 2", "TSK-203", "US-008", "Create formula script computing total face detection duration against total exam elapsed time.", "TSK-202", "Medium", "Development Team", "3- Completed", "Face Presence Ratio Metric"],
    ["Sprint 2", "TSK-204", "US-009", "Develop frontend JS listeners for visibilitychange, blur, focus, and fullscreen key events.", "TSK-104", "High", "Development Team", "3- Completed", "Browser Monitoring Script"],
    ["Sprint 2", "TSK-205", "US-010", "Implement rule-engine filtering to parse client event logs and flag threshold breaches.", "TSK-202, TSK-204", "High", "Development Team", "3- Completed", "Suspicious Event Detection Engine"],

    # Sprint 3
    ["Sprint 3", "TSK-301", "US-011", "Implement weighted deduction model subtracting points based on violation type and duration.", "TSK-205", "High", "Development Team", "3- Completed", "Integrity Scoring Module"],
    ["Sprint 3", "TSK-302", "US-012", "Implement categorization rules mapping numerical integrity scores into Low, Medium, High risk flags.", "TSK-301", "High", "Development Team", "3- Completed", "Risk Classification Logic"],
    ["Sprint 3", "TSK-303", "US-013", "Construct LangChain prompt templates parsing structured evidence logs into natural language reports.", "TSK-302", "High", "Development Team", "3- Completed", "LangChain LLM Reporter Module"],
    ["Sprint 3", "TSK-304", "US-014", "Set up database tables for persistent logging of alerts, violation types, and timestamped evidence.", "TSK-205", "Medium", "Development Team", "3- Completed", "Evidence & Alert Repository"],
    ["Sprint 3", "TSK-305", "US-015", "Write Pandas analysis routines summarizing candidate performance and monitoring statistics.", "TSK-304", "Medium", "Development Team", "3- Completed", "Pandas Analytics Engine"],
    ["Sprint 3", "TSK-306", "US-016", "Generate Matplotlib and Seaborn charts displaying class-wide violation frequencies and risk profiles.", "TSK-305", "Low", "Development Team", "3- Completed", "Seaborn Plot Generator Script"],
    ["Sprint 3", "TSK-307", "US-017", "Train Scikit-learn K-Means model to cluster exam sessions into behavioral anomaly groups.", "TSK-305", "Low", "Development Team", "3- Completed", "K-Means Session Profiler Module"],

    # Sprint 4
    ["Sprint 4", "TSK-401", "US-018", "Develop multi-page Streamlit web application layout with live invigilator monitoring tables.", "TSK-305", "High", "Development Team", "3- Completed", "Streamlit Admin Dashboard"],
    ["Sprint 4", "TSK-402", "US-019", "Create JSON and CSV exporter utilities allowing invigilators to download audit reports.", "TSK-401", "Medium", "Development Team", "3- Completed", "JSON/CSV Export Engine"],
    ["Sprint 4", "TSK-403", "US-020", "Run comprehensive end-to-end integration tests across webcam feeds, browser events, and reporting.", "TSK-401", "High", "Development Team", "3- Completed", "Integration Test Suite Results"],
    ["Sprint 4", "TSK-404", "US-021", "Finalize project README, setup instructions, code inline comments, and GitHub repository.", "TSK-403", "High", "Development Team", "3- Completed", "Complete GitHub Project Repo"]
]

for row in sb_data:
    ws_sb.append(row)

# ---------------------------------------------------------
# 3. STAND UP MEETING
# ---------------------------------------------------------
su_headers = ["Sprint", "Meeting / Week", "Team Member", "What was completed?", "What is planned next?", "Blockers / Issues", "Action / Follow-up"]
ws_su.append(su_headers)

su_data = [
    ["Sprint 1", "Week 1", "Development Team", "Flask project structure, database models, and SQLite setup.", "Implement registration, user login, and password hashing.", "Database schema alignment across candidate and session models.", "Standardized SQLite table creation scripts and initial migration workflow."],
    ["Sprint 1", "Week 2", "Development Team", "Candidate authentication, photo capture during registration, and exam lifecycle endpoints.", "Integrate OpenCV Haar Cascade face detection pipeline.", "Handling camera permissions across different web browser types.", "Added fallback UI instructions asking candidates to allow camera access."],
    
    ["Sprint 2", "Week 3", "Development Team", "OpenCV Haar Cascade face presence integration and absence tracking logic.", "Develop JavaScript client event listeners for browser activity.", "Subtle illumination changes causing false face absence triggers.", "Adjusted Haar Cascade scaling parameters and set continuous absence time thresholds."],
    ["Sprint 2", "Week 4", "Development Team", "Browser tab switching, window focus loss, and keypress detection listeners.", "Develop rule-based integrity deduction engine.", "Duplicate focus-loss events firing simultaneously on browser window switch.", "Implemented client-side event debouncing and backend duplicate filtering."],
    
    ["Sprint 3", "Week 5", "Development Team", "Weighted integrity score calculation engine and Low/Medium/High risk classification.", "Integrate LangChain and LLM framework for natural-language reporting.", "Preventing duplicate integrity point deductions for overlapping events.", "Unified violation event queue to calculate net score deductions sequentially."],
    ["Sprint 3", "Week 6", "Development Team", "LangChain LLM summary generation, evidence store, and Pandas analytics script.", "Build Streamlit administrative and invigilator dashboard.", "LLM API response latency when generating long text reports.", "Implemented prompt truncation and structured response formatting for rapid generation."],
    
    ["Sprint 4", "Week 7", "Development Team", "Streamlit dashboard views for live monitoring, score displays, and JSON/CSV exports.", "Execute full system integration and automated regression tests.", "Streamlit auto-refreshing causing temporary lag during heavy data renders.", "Optimized Streamlit caching using @st.cache_data for analytics processing."],
    ["Sprint 4", "Week 8", "Development Team", "Complete system integration testing, automated regression suite execution, and documentation.", "Final repository cleanup and submission packaging.", "Minor layout glitches on smaller screen resolutions in dashboard view.", "Updated CSS layout rules, finalized documentation, and published GitHub repository."]
]

for row in su_data:
    ws_su.append(row)

# ---------------------------------------------------------
# 4. RETROSPECTION
# ---------------------------------------------------------
re_headers = ["Sprint", "What Went Well", "What Could Be Improved", "Challenges / Lessons Learned", "Action Items", "Owner"]
ws_re.append(re_headers)

re_data = [
    ["Sprint 1", "Flask architecture and database schema were configured quickly and cleanly.", "Initial database schema lacked flexible fields for storing raw camera frame metadata.", "Ensuring database migration consistency early prevents breaking schema updates later.", "Maintain modular database migrations and standardized initialization scripts.", "Development Team"],
    ["Sprint 2", "OpenCV Haar Cascade and browser event tracking were successfully integrated.", "Occasional duplicate focus-loss logs were recorded during rapid tab switching.", "Browser event implementations differ slightly across Chrome, Firefox, and Edge.", "Added event debouncing in JavaScript and robust backend event deduplication.", "Development Team"],
    ["Sprint 3", "Integrity scoring rules, K-Means clustering, and LangChain reporting integrated smoothly.", "External LLM API call times required handling to avoid endpoint delay.", "Formatting unstructured evidence logs into structured LLM prompts is critical for consistent output.", "Refined LangChain prompt templates and cached repetitive analytics calculations.", "Development Team"],
    ["Sprint 4", "Streamlit provided an intuitive and responsive admin interface with full export support.", "Need for broader manual webcam validation across varied lighting environments.", "Proctoring tools require careful calibration between strict detection and avoiding false positives.", "Added configurable threshold settings so invigilators can tweak sensitivity.", "Development Team"]
]

for row in re_data:
    ws_re.append(row)

# ---------------------------------------------------------
# GLOBAL FORMATTING & STYLING
# ---------------------------------------------------------
sheets = [ws_pb, ws_sb, ws_su, ws_re]

for ws in sheets:
    ws.views.sheetView[0].showGridLines = True
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # Style Header Row
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border
    
    ws.row_dimensions[1].height = 28

    # Style Data Rows
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            cell.font = data_font
            cell.border = thin_border
            
            # Alignments
            if cell.column in [1, 2, 3, 5, 8]:  # Sprint, IDs, Status, Priority
                cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)

    # Auto-adjust column widths cleanly
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        
        for cell in col:
            val_str = str(cell.value or '')
            if '\n' in val_str:
                lines = val_str.split('\n')
                max_len = max(max_len, max(len(l) for l in lines))
            else:
                max_len = max(max_len, len(val_str))
        
        # Set explicit reasonable column widths
        if col_letter in ['D', 'E', 'F', 'G']:  # Long text columns
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 15), 45)
        else:
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 25)

# Save the workbook
wb.save("ExamGuard_Agile_Documentation.xlsx")
print("Successfully generated ExamGuard_Agile_Documentation.xlsx!")