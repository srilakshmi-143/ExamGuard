document.addEventListener('DOMContentLoaded', async () => {
    const video = document.getElementById('verifyVideo');
    const canvas = document.getElementById('verifyCanvas');
    const statusBox = document.getElementById('verifyStatusBox');
    const statusText = document.getElementById('verifyStatusText');
    const spinner = document.getElementById('verifySpinner');
    const runBtn = document.getElementById('runVerifyBtn');
    const proceedBtn = document.getElementById('proceedBtn');

    let stream = null;

    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        runBtn.disabled = false;
        statusText.textContent = 'Webcam active. Click "Capture & Verify Identity" to perform verification.';
        if (spinner) spinner.style.display = 'none';
    } catch (e) {
        statusText.textContent = 'Camera access denied. Verification cannot proceed.';
        statusBox.className = 'verify-status-box error';
    }

    runBtn.addEventListener('click', () => {
        statusText.textContent = 'Capturing frame and processing facial verification via OpenCV...';
        statusBox.className = 'verify-status-box info';
        runBtn.disabled = true;

        const ctx = canvas.getContext('2d');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const frameData = canvas.toDataURL('image/jpeg');

        fetch('/api/verify_identity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: SESSION_TOKEN, frame: frameData })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                statusText.textContent = `VERIFICATION SUCCESSFUL (${data.confidence}% Match Confidence). ${data.message}`;
                statusBox.className = 'verify-status-box success';
                proceedBtn.style.display = 'inline-flex';
                runBtn.style.display = 'none';
            } else {
                statusText.textContent = `VERIFICATION FAILED: ${data.message}`;
                statusBox.className = 'verify-status-box error';
                runBtn.disabled = false;
            }
        })
        .catch(err => {
            statusText.textContent = 'Server processing error during verification.';
            statusBox.className = 'verify-status-box error';
            runBtn.disabled = false;
        });
    });
});