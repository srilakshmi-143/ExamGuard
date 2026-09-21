document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('webcamVideo');
    const canvas = document.getElementById('photoCanvas');
    const preview = document.getElementById('capturedPreview');
    const startCamBtn = document.getElementById('startCamBtn');
    const captureBtn = document.getElementById('captureBtn');
    const retakeBtn = document.getElementById('retakeBtn');
    const submitBtn = document.getElementById('submitBtn');
    const photoDataInput = document.getElementById('photoData');
    const camStatus = document.getElementById('camStatus');

    let stream = null;

    startCamBtn.addEventListener('click', async () => {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            video.srcObject = stream;
            video.style.display = 'block';
            preview.style.display = 'none';
            startCamBtn.style.display = 'none';
            captureBtn.style.display = 'inline-flex';
            camStatus.textContent = 'Camera Status: Live & Ready';
            camStatus.style.color = 'green';
        } catch (err) {
            camStatus.textContent = 'Camera Access Denied or Unavailable!';
            camStatus.style.color = 'red';
        }
    });

    captureBtn.addEventListener('click', () => {
        const context = canvas.getContext('2d');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        const dataUrl = canvas.toDataURL('image/jpeg');
        photoDataInput.value = dataUrl;

        preview.src = dataUrl;
        preview.style.display = 'block';
        video.style.display = 'none';

        captureBtn.style.display = 'none';
        retakeBtn.style.display = 'inline-flex';
        submitBtn.disabled = false;
        camStatus.textContent = 'Photograph Captured Successfully';
    });

    retakeBtn.addEventListener('click', () => {
        preview.style.display = 'none';
        video.style.display = 'block';
        retakeBtn.style.display = 'none';
        captureBtn.style.display = 'inline-flex';
        photoDataInput.value = '';
        submitBtn.disabled = true;
        camStatus.textContent = 'Camera Status: Live';
    });
});