let currentQuestionIndex = 1;

document.addEventListener('DOMContentLoaded', () => {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitExamBtn');
    const currentQNumSpan = document.getElementById('currentQNum');
    const progressBar = document.getElementById('questionProgressBar');

    function updateQuestionView() {
        for (let i = 1; i <= TOTAL_QUESTIONS; i++) {
            const qBlock = document.getElementById(`qBlock_${i}`);
            if (qBlock) qBlock.style.display = (i === currentQuestionIndex) ? 'block' : 'none';
        }

        currentQNumSpan.textContent = currentQuestionIndex;
        const progressPercent = (currentQuestionIndex / TOTAL_QUESTIONS) * 100;
        progressBar.style.width = `${progressPercent}%`;

        prevBtn.disabled = (currentQuestionIndex === 1);

        if (currentQuestionIndex === TOTAL_QUESTIONS) {
            nextBtn.style.display = 'none';
            submitBtn.style.display = 'inline-flex';
        } else {
            nextBtn.style.display = 'inline-flex';
            submitBtn.style.display = 'none';
        }
    }

    prevBtn.addEventListener('click', () => {
        if (currentQuestionIndex > 1) {
            currentQuestionIndex--;
            updateQuestionView();
        }
    });

    nextBtn.addEventListener('click', () => {
        if (currentQuestionIndex < TOTAL_QUESTIONS) {
            currentQuestionIndex++;
            updateQuestionView();
        }
    });

    // Auto-save selections via API
    document.querySelectorAll('input[type="radio"]').forEach(radio => {
        radio.addEventListener('change', (e) => {
            const questionBlock = e.target.closest('.question-block');
            const questionId = questionBlock.getAttribute('data-qid');
            const selectedOption = e.target.value;

            fetch('/api/save_answer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    token: SESSION_TOKEN,
                    question_id: questionId,
                    selected_option: selectedOption
                })
            });
        });
    });

    // Countdown Timer
    let totalSeconds = DURATION_MINUTES * 60;
    const timerText = document.getElementById('timerText');

    const timerInterval = setInterval(() => {
        totalSeconds--;
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        timerText.textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;

        if (totalSeconds <= 0) {
            clearInterval(timerInterval);
            alert('Time has expired! Submitting your examination automatically.');
            document.getElementById('submitForm').submit();
        }
    }, 1000);
});