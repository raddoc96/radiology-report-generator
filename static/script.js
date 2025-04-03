document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('report-form');
    const generateButton = document.getElementById('generate-button');
    const loadingDiv = document.getElementById('loading');
    const resultArea = document.getElementById('result-area');
    const reportOutput = document.getElementById('report-output');
    const errorArea = document.getElementById('error-area');
    const errorMessage = document.getElementById('error-message');
    const copyButton = document.getElementById('copy-button');

    form.addEventListener('submit', async (event) => {
        event.preventDefault(); // Prevent default form submission

        // Hide previous results/errors and show loading
        resultArea.style.display = 'none';
        errorArea.style.display = 'none';
        loadingDiv.style.display = 'block';
        generateButton.disabled = true;
        reportOutput.textContent = ''; // Clear previous report
        errorMessage.textContent = ''; // Clear previous error

        const findings = document.getElementById('findings').value;
        const template = document.getElementById('template').value;

        try {
            const response = await fetch('/generate_report', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ findings, template }),
            });

            if (!response.ok) {
                // Try to get error message from backend response
                let errorMsg = `HTTP error! Status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorMsg;
                } catch (e) {
                    // Ignore if response is not JSON
                }
                throw new Error(errorMsg);
            }

            const data = await response.json();

            if (data.report) {
                reportOutput.textContent = data.report;
                resultArea.style.display = 'block';
            } else if (data.error) {
                 throw new Error(data.error);
            } else {
                throw new Error("Received an unexpected response from the server.");
            }

        } catch (error) {
            console.error('Error generating report:', error);
            errorMessage.textContent = `Failed to generate report: ${error.message}`;
            errorArea.style.display = 'block';
        } finally {
            // Hide loading and re-enable button
            loadingDiv.style.display = 'none';
            generateButton.disabled = false;
        }
    });

    // Copy to clipboard functionality
    copyButton.addEventListener('click', () => {
        navigator.clipboard.writeText(reportOutput.textContent)
            .then(() => {
                // Optional: Give user feedback (e.g., change button text)
                copyButton.textContent = 'Copied!';
                setTimeout(() => { copyButton.textContent = 'Copy Report to Clipboard'; }, 2000); // Reset after 2s
            })
            .catch(err => {
                console.error('Failed to copy text: ', err);
                // Optional: Show an error message to the user
                 alert("Failed to copy report. Please copy manually.");
            });
    });
});