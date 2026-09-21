document.addEventListener('DOMContentLoaded', async () => {
    const video = document.getElementById('examWebcam');
    const canvas = document.getElementById('examCanvas');
    const faceStatusEl = document.getElementById('faceStatus');
    const faceCountEl = document.getElementById('faceCount');
    const tabSwitchEl = document.getElementById('tabSwitchCount');
    const integrityDisplay = document.getElementById('integrityScoreDisplay');
    const integrityBar = document.getElementById('integrityBar');

    let noFaceDurationSeconds = 0;
    let tabSwitches = 0;

    // Start Webcam
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
        video.srcObject = stream;
    } catch (e) {
        console.error("Proctoring camera initialization failed.");
    }

    // 1. Send Webcam Frames Every 1 Second to Backend Flask/OpenCV
    setInterval(() => {
        if (!video.videoWidth) return;

        const ctx = canvas.getContext('2d');
        canvas.width = 320;
        canvas.height = 240;
        ctx.drawImage(video, 0, 0, 320, 240);
        const frameData = canvas.toDataURL('image/jpeg', 0.6);

        fetch('/api/process_frame', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                token: SESSION_TOKEN,
                frame: frameData,
                no_face_duration: noFaceDurationSeconds
            })
        })
        .then(res => res.json())
        .then(data => {
            // Update UI status
            faceStatusEl.textContent = data.face_status;
            faceCountEl.textContent = data.face_count;
            integrityDisplay.textContent = data.integrity_score;
            integrityBar.style.width = `${data.integrity_score}%`;

            if (data.face_status === 'NO_FACE') {
                noFaceDurationSeconds += 1;
                faceStatusEl.style.color = 'red';
            } else {
                noFaceDurationSeconds = 0; // Reset continuous timer if face returns
                faceStatusEl.style.color = 'green';
            }

            if (data.action === 'TERMINATE') {
                window.location.href = `/exam/terminated/${SESSION_TOKEN}`;
            }
        });
    }, 1000);

    // 2. Browser Security & Violation Handlers
    function logBrowserViolation(eventType, details) {
        fetch('/api/log_browser_event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: SESSION_TOKEN, event_type: eventType, details: details })
        })
        .then(res => res.json())
        .then(data => {
            if (eventType === 'TAB_SWITCH') {
                tabSwitches++;
                tabSwitchEl.textContent = `${tabSwitches} / 3`;
            }
            if (data.current_integrity_score !== undefined) {
                integrityDisplay.textContent = data.current_integrity_score;
                integrityBar.style.width = `${data.current_integrity_score}%`;
            }
            if (data.action === 'TERMINATE') {
                window.location.href = `/exam/terminated/${SESSION_TOKEN}`;
            }
        });
    }

    // Event Listeners
    window.addEventListener('blur', () => logBrowserViolation('TAB_SWITCH', 'User navigated away from exam tab/window'));
    document.addEventListener('fullscreenchange', () => {
        if (!document.fullscreenElement) {
            logBrowserViolation('FULLSCREEN_EXIT', 'User exited browser fullscreen mode');
        }
    });

    document.addEventListener('copy', (e) => { e.preventDefault(); logBrowserViolation('COPY_ATTEMPT', 'Clipboard copy attempted'); });
    document.addEventListener('paste', (e) => { e.preventDefault(); logBrowserViolation('PASTE_ATTEMPT', 'Clipboard paste attempted'); });
    document.addEventListener('contextmenu', (e) => e.preventDefault());
});