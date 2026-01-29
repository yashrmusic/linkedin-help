document.addEventListener('DOMContentLoaded', () => {
    const profileSelect = document.getElementById('profile');
    const btnGenerate = document.getElementById('btnGenerate');
    const btnSend = document.getElementById('btnSend');
    const logContainer = document.getElementById('logContainer');
    const resultLinks = document.getElementById('resultLinks');
    const pdfLinkContainer = document.getElementById('pdfLinkContainer');
    const offerForm = document.getElementById('offerForm');
    const aiPrompt = document.getElementById('aiPrompt');
    const btnAiFill = document.getElementById('btnAiFill');

    let currentPdfUrl = null;
    let currentCandidateData = null;

    // Load available profiles
    async function loadProfiles() {
        try {
            const response = await fetch('/api/profiles');
            const data = await response.json();
            if (data.success) {
                data.profiles.forEach(profile => {
                    const option = document.createElement('option');
                    option.value = profile;
                    option.textContent = profile.charAt(0).toUpperCase() + profile.slice(1);
                    profileSelect.appendChild(option);
                });
                addLog('Profiles loaded successfully.', 'info');
            }
        } catch (error) {
            addLog(`Error loading profiles: ${error.message}`, 'error');
        }
    }

    function addLog(message, type = 'info') {
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        const time = new Date().toLocaleTimeString();
        entry.textContent = `[${time}] ${message}`;
        logContainer.appendChild(entry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Generate Offer
    btnGenerate.addEventListener('click', async () => {
        if (!offerForm.checkValidity()) {
            offerForm.reportValidity();
            return;
        }

        const formData = new FormData(offerForm);
        const profile = profileSelect.value;
        const candidateDetails = {
            name: document.getElementById('name').value,
            email: document.getElementById('email').value,
            phone: document.getElementById('phone').value,
            position: document.getElementById('position').value,
            start_date: document.getElementById('start_date').value,
            salary: document.getElementById('salary').value,
            test_date: document.getElementById('test_date').value
        };

        btnGenerate.disabled = true;
        btnGenerate.innerHTML = '⏳ Generating...';
        addLog(`Generating offer for ${candidateDetails.name}...`, 'info');

        try {
            const response = await fetch('/api/generate-offer', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile: profile,
                    candidate: candidateDetails
                })
            });

            const result = await response.json();
            if (result.success) {
                addLog(`Success! PDF generated.`, 'success');
                currentPdfUrl = result.pdf_url;
                currentCandidateData = candidateDetails;

                resultLinks.style.display = 'block';
                pdfLinkContainer.innerHTML = `
                    <a href="${result.pdf_url}" target="_blank" class="btn btn-outline" style="display: block; margin-bottom: 5px;">
                        📄 View Generated PDF
                    </a>
                `;
                btnSend.disabled = false;
            } else {
                addLog(`Error: ${result.message}`, 'error');
            }
        } catch (error) {
            addLog(`Request failed: ${error.message}`, 'error');
        } finally {
            btnGenerate.disabled = false;
            btnGenerate.innerHTML = '📝 Generate PDF';
        }
    });

    // Send Email
    btnSend.addEventListener('click', async () => {
        if (!currentCandidateData) return;

        btnSend.disabled = true;
        btnSend.innerHTML = '⏳ Sending...';
        addLog(`Sending email to ${currentCandidateData.email}...`, 'info');

        try {
            const response = await fetch('/api/send-email', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    profile: profileSelect.value,
                    candidate_name: currentCandidateData.name,
                    candidate_email: currentCandidateData.email
                })
            });

            const result = await response.json();
            if (result.success) {
                addLog(`Email sent successfully to ${currentCandidateData.name}!`, 'success');
            } else {
                addLog(`Failed to send email: ${result.message}`, 'error');
            }
        } catch (error) {
            addLog(`Email request failed: ${error.message}`, 'error');
        } finally {
            btnSend.disabled = false;
            btnSend.innerHTML = '📤 Send Email';
        }
    });

    loadProfiles();

    // AI Smart Fill
    btnAiFill.addEventListener('click', async () => {
        const prompt = aiPrompt.value.trim();
        if (!prompt) {
            addLog('Please enter some text in the AI box first.', 'error');
            return;
        }

        btnAiFill.disabled = true;
        btnAiFill.innerHTML = '⏳ AI is thinking...';
        addLog('AI is parsing your text...', 'info');

        try {
            const response = await fetch('/api/ai-parse', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: prompt })
            });

            const result = await response.json();
            if (result.success) {
                const data = result.data;
                // Auto-fill form fields
                if (data.name) document.getElementById('name').value = data.name;
                if (data.email) document.getElementById('email').value = data.email;
                if (data.phone) document.getElementById('phone').value = data.phone;
                if (data.position) document.getElementById('position').value = data.position;
                if (data.start_date) document.getElementById('start_date').value = data.start_date;
                if (data.salary) document.getElementById('salary').value = data.salary;
                if (data.test_date) document.getElementById('test_date').value = data.test_date;

                addLog('Form filled by AI! Please review and click Generate.', 'success');
            } else {
                addLog(`AI Parsing failed: ${result.message}`, 'error');
            }
        } catch (error) {
            addLog(`AI Request failed: ${error.message}`, 'error');
        } finally {
            btnAiFill.disabled = false;
            btnAiFill.innerHTML = '🤖 AI Smart Fill Form';
        }
    });
});
