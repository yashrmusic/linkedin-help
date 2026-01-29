// Initialize signature pad using the library
const canvas = document.getElementById('signaturePad');
const signaturePad = new SignaturePad(canvas, {
    backgroundColor: 'rgba(255, 255, 255, 0)',
    penColor: 'rgb(0, 0, 0)'
});

// Set canvas actual size
function resizeCanvas() {
    const ratio = Math.max(window.devicePixelRatio || 1, 1);
    canvas.width = canvas.offsetWidth * ratio;
    canvas.height = canvas.offsetHeight * ratio;
    canvas.getContext("2d").scale(ratio, ratio);
    signaturePad.clear(); // otherwise isEmpty() might return incorrect value
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// Clear signature
document.getElementById('clearSignature').addEventListener('click', () => {
    signaturePad.clear();
    checkFormValidity();
});

// Undo last stroke
document.getElementById('undoSignature').addEventListener('click', () => {
    const data = signaturePad.toData();
    if (data) {
        data.pop(); // remove last stroke
        signaturePad.fromData(data);
    }
    checkFormValidity();
});

// Form validation
const agreeCheckbox = document.getElementById('agreeTerms');
const dateInput = document.getElementById('signatureDate');
const submitButton = document.getElementById('submitSignature');

agreeCheckbox.addEventListener('change', checkFormValidity);
dateInput.addEventListener('change', checkFormValidity);
canvas.addEventListener('mouseup', checkFormValidity);
canvas.addEventListener('touchend', checkFormValidity);

function checkFormValidity() {
    const hasSignature = !signaturePad.isEmpty();
    const hasAgreed = agreeCheckbox.checked;
    const hasDate = dateInput.value !== '';

    submitButton.disabled = !(hasSignature && hasAgreed && hasDate);
}

// Set today's date as default
const today = new Date().toISOString().split('T')[0];
dateInput.value = today;
checkFormValidity();

// Get URL parameters
function getUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        candidate: params.get('candidate') || 'Mariya_Fatima',
        profile: params.get('profile') || 'melange'
    };
}

// Load offer letter preview
async function loadOfferPreview() {
    const { candidate, profile } = getUrlParams();

    try {
        const response = await fetch(`/api/offer-preview/${candidate}?profile=${profile}`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('offerPreview').innerHTML = `
                <h3>Dear ${data.candidate.name},</h3>
                <p>Further to the personal interview held on <strong>${data.candidate.interview_date}</strong>, 
                <strong>${profile === 'melange' ? 'The Melange Studio' : profile}</strong> is pleased to offer you employment as <strong>${data.candidate.position}</strong> 
                starting <strong>${data.candidate.start_date}</strong>.</p>
                
                <p><strong>Compensation Details:</strong></p>
                <ul>
                    <li>Monthly Salary: ₹${data.candidate.salary}</li>
                    <li>Probation Period: 3 months</li>
                </ul>
                
                <p class="note">Click "View Full PDF" to see the complete offer letter.</p>
            `;
        }
    } catch (error) {
        document.getElementById('offerPreview').innerHTML = `
            <p class="error">Unable to load offer preview. Please contact HR.</p>
        `;
    }
}

loadOfferPreview();

// View full PDF
document.getElementById('viewFullPdf').addEventListener('click', () => {
    const { candidate, profile } = getUrlParams();
    window.open(`/api/offer-pdf/${candidate}?profile=${profile}`, '_blank');
});

// Submit signature
submitButton.addEventListener('click', async () => {
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="icon">⏳</span> Submitting...';

    const statusMessage = document.getElementById('statusMessage');
    statusMessage.className = 'status-message';
    statusMessage.style.display = 'none';

    try {
        if (signaturePad.isEmpty()) {
            throw new Error('Please provide your signature');
        }

        // Convert canvas to image
        const signatureData = signaturePad.toDataURL('image/png');
        const { candidate, profile } = getUrlParams();

        const response = await fetch('/api/submit-signature', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                candidate: candidate,
                profile: profile,
                signature: signatureData,
                date: dateInput.value
            })
        });

        const result = await response.json();

        if (result.success) {
            statusMessage.className = 'status-message success';
            statusMessage.style.display = 'block';
            statusMessage.textContent = '✅ Signature submitted successfully! Your signed offer letter has been generated.';
            submitButton.innerHTML = '<span class="icon">✓</span> Submitted Successfully!';

            // Download signed PDF
            setTimeout(() => {
                window.location.href = result.signed_pdf_url;
            }, 2000);
        } else {
            throw new Error(result.message || 'Submission failed');
        }
    } catch (error) {
        statusMessage.className = 'status-message error';
        statusMessage.style.display = 'block';
        statusMessage.textContent = `❌ Error: ${error.message}`;
        submitButton.disabled = false;
        submitButton.innerHTML = '<span class="icon">✓</span> Submit Signature & Accept Offer';
    }
});
