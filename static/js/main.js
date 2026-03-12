document.addEventListener('DOMContentLoaded', function () {
    // Global state
    const state = {
        currentStep: 1,
        uploadedFile: null,
        fileName: null,
        subject: '',
        topics: [],
        selectedTopics: [],
        generatedQuestions: [],
        questionBank: []  // This would be populated from an external source in a real app
    };

    // DOM Elements
    const fileInput = document.getElementById('file-input');
    const dragDropArea = document.getElementById('drag-drop-area');
    const subjectInput = document.getElementById('subject-input');
    const subjectDetailsInput = document.getElementById('subject-details-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const fileDetails = document.getElementById('file-details');
    const fileName = document.getElementById('file-name');
    const contentPreview = document.getElementById('content-preview');
    const removeFileBtn = document.getElementById('remove-file');
    const topicsContainer = document.getElementById('topics-container');
    const selectAllTopicsBtn = document.getElementById('select-all-topics');
    const deselectAllTopicsBtn = document.getElementById('deselect-all-topics');
    const generateQuestionsBtn = document.getElementById('generate-questions-btn');
    const backToStep1Btn = document.getElementById('back-to-step-1');
    const backToStep2Btn = document.getElementById('back-to-step-2');
    const questionsContainer = document.getElementById('questions-container');
    const examTitleInput = document.getElementById('exam-title');
    const includeAnswersCheck = document.getElementById('include-answers');
    const exportPdfBtn = document.getElementById('export-pdf');
    const exportHtmlBtn = document.getElementById('export-html');
    const exportMdBtn = document.getElementById('export-md');
    const regenerateBtn = document.getElementById('regenerate-btn');
    const progressBar = document.getElementById('progress-bar');

    // Step indicators
    const step1Dot = document.getElementById('step-1');
    const step2Dot = document.getElementById('step-2');
    const step3Dot = document.getElementById('step-3');
    const step1Content = document.getElementById('step-1-content');
    const step2Content = document.getElementById('step-2-content');
    const step3Content = document.getElementById('step-3-content');

    // Toast elements
    const toast = document.getElementById('toast');
    const toastTitle = document.getElementById('toast-title');
    const toastMessage = document.getElementById('toast-message');
    const bsToast = new bootstrap.Toast(toast);

    // Event Listeners for File Upload
    fileInput.addEventListener('change', handleFileSelect);
    dragDropArea.addEventListener('dragover', handleDragOver);
    dragDropArea.addEventListener('dragleave', handleDragLeave);
    dragDropArea.addEventListener('drop', handleDrop);
    removeFileBtn.addEventListener('click', handleRemoveFile);

    // Event Listener for Subject Input
    subjectInput.addEventListener('input', validateInputs);

    // Event Listeners for Navigation
    analyzeBtn.addEventListener('click', handleAnalyze);
    backToStep1Btn.addEventListener('click', () => navigateToStep(1));
    backToStep2Btn.addEventListener('click', () => navigateToStep(2));

    // Event Listeners for Topic Selection
    selectAllTopicsBtn.addEventListener('click', selectAllTopics);
    deselectAllTopicsBtn.addEventListener('click', deselectAllTopics);

    // Event Listeners for Question Generation
    generateQuestionsBtn.addEventListener('click', handleGenerateQuestions);
    regenerateBtn.addEventListener('click', handleGenerateQuestions);

    // Event Listeners for Export
    exportPdfBtn.addEventListener('click', () => exportPaper('pdf'));
    exportHtmlBtn.addEventListener('click', () => exportPaper('html'));
    exportMdBtn.addEventListener('click', () => exportPaper('md'));

    // Mode and Rate Limit Logic
    let currentMode = localStorage.getItem('gemini_mode') || 'pro';
    const modeProBtn = document.getElementById('mode-pro');
    const modeFastBtn = document.getElementById('mode-fast');
    const modelSelect = document.getElementById('model-select');
    const quotaText = document.getElementById('quota-text');
    const quotaFill = document.getElementById('quota-fill');
    const apiKeyInput = document.getElementById('api-key-input');

    const DAILY_LIMITS = {
        "pro": { "3.1": 50, "2.5": 50 },
        "flash": { "3.1": 1500, "2.5": 1500 },
        "flash-lite": { "3.1": 1500, "2.5": 1500 }
    };

    function updateQuotaDisplay() {
        const stored = localStorage.getItem("qpg_rate_limits");
        const today = new Date().toISOString().slice(0, 10);
        let limits = { date: today, used: {} };
        if (stored) {
            const p = JSON.parse(stored);
            if (p.date === today) limits = p;
        }
        const tier = currentMode === "pro" ? "pro" : "flash";
        const limit = DAILY_LIMITS[tier]?.["2.5"] || 25;
        const used = limits.used[tier] || 0;
        const remaining = Math.max(0, limit - used);

        quotaText.textContent = `Quota: ${remaining} / ${limit}`;
        const pct = Math.max(0, Math.min(100, (remaining / limit) * 100));
        quotaFill.style.width = pct + '%';

        quotaFill.className = 'progress-bar bg-info';
        quotaText.className = 'badge bg-info text-dark';
        if (pct <= 50 && pct > 20) {
            quotaFill.className = 'progress-bar bg-warning';
            quotaText.className = 'badge bg-warning text-dark';
        } else if (pct <= 20) {
            quotaFill.className = 'progress-bar bg-danger';
            quotaText.className = 'badge bg-danger';
        }
    }

    function trackUsage(modelName) {
        const tier = modelName.includes("pro") ? "pro" : modelName.includes("flash-lite") ? "flash-lite" : "flash";
        const stored = localStorage.getItem("qpg_rate_limits");
        const today = new Date().toISOString().slice(0, 10);
        let limits = { date: today, used: {} };
        if (stored) {
            const p = JSON.parse(stored);
            if (p.date === today) limits = p;
        }
        limits.used[tier] = (limits.used[tier] || 0) + 1;
        localStorage.setItem("qpg_rate_limits", JSON.stringify(limits));
        updateQuotaDisplay();
    }

    function setModeUI(mode) {
        currentMode = mode;
        localStorage.setItem('gemini_mode', mode);

        if (mode === 'pro') {
            modeProBtn.classList.replace('btn-outline-info', 'btn-info');
            modeProBtn.style.color = '#05080f';
            modeFastBtn.classList.replace('btn-info', 'btn-outline-info');
            modeFastBtn.style.color = '';

            modelSelect.innerHTML = `
                <option value="gemini-3.1-pro-preview">Gemini 3.1 Pro</option>
            `;
        } else {
            modeFastBtn.classList.replace('btn-outline-info', 'btn-info');
            modeFastBtn.style.color = '#05080f';
            modeProBtn.classList.replace('btn-info', 'btn-outline-info');
            modeProBtn.style.color = '';

            modelSelect.innerHTML = `
                <option value="gemini-3.1-flash-lite-preview">Gemini 3.1 Flash Lite</option>
            `;
        }

        const savedModel = localStorage.getItem('gemini_model');
        if (savedModel && Array.from(modelSelect.options).some(o => o.value === savedModel)) {
            modelSelect.value = savedModel;
        }
        updateQuotaDisplay();
    }

    if (modeProBtn && modeFastBtn) {
        modeProBtn.addEventListener('click', () => setModeUI('pro'));
        modeFastBtn.addEventListener('click', () => setModeUI('fast'));
    }

    if (modelSelect) {
        modelSelect.addEventListener('change', (e) => {
            localStorage.setItem('gemini_model', e.target.value);
        });
    }

    if (apiKeyInput) {
        apiKeyInput.value = localStorage.getItem('gemini_api_key') || '';
        apiKeyInput.addEventListener('change', (e) => {
            localStorage.setItem('gemini_api_key', e.target.value);
        });
    }

    // Initialize UI
    setModeUI(currentMode);

    // Helper for API headers
    function getApiHeaders() {
        const headers = {};
        const apiKey = document.getElementById('api-key-input')?.value?.trim();
        if (apiKey) headers['X-Gemini-Api-Key'] = apiKey;
        const modelName = document.getElementById('model-select')?.value;
        if (modelName) headers['X-Gemini-Model-Name'] = modelName;
        return headers;
    }

    // File Upload Handlers
    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            processFile(file);
        }
    }

    function handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        dragDropArea.classList.add('drag-active');
    }

    function handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        dragDropArea.classList.remove('drag-active');
    }

    function handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        dragDropArea.classList.remove('drag-active');

        if (e.dataTransfer.files.length) {
            const file = e.dataTransfer.files[0];
            processFile(file);
        }
    }

    async function processFile(file) {
        // Check file type
        const validTypes = [
            'application/pdf',
            'text/plain',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/json',
            'text/markdown'
        ];

        if (!validTypes.includes(file.type)) {
            showToast('Error', 'Invalid file type. Please upload PDF, TXT, DOCX, JSON, or Markdown files.');
            return;
        }

        // Update state
        state.uploadedFile = file;
        state.fileName = file.name;

        // Update UI
        fileName.textContent = file.name;
        fileDetails.classList.remove('d-none');

        // Enable analyze button if subject is also filled
        validateInputs();
    }

    function handleRemoveFile() {
        // Clear state
        state.uploadedFile = null;
        state.fileName = null;

        // Update UI
        fileDetails.classList.add('d-none');
        fileInput.value = '';
        analyzeBtn.disabled = true;
    }

    function validateInputs() {
        const subjectFilled = subjectInput.value.trim() !== '';
        // Allow generating without file if subject is filled
        analyzeBtn.disabled = !subjectFilled;
    }

    // Content Analysis
    async function handleAnalyze() {
        if (!subjectInput.value.trim()) {
            showToast('Error', 'Please enter a subject name.');
            return;
        }

        showProgress();

        try {
            // STEP 1: Direct Browser Upload to Gemini (Bypasses Vercel 4.5MB limit)
            const file = state.uploadedFile;
            const apiKey = window.gemini ? window.gemini.getApiKey() : (document.getElementById('api-key-input')?.value?.trim() || '');
            
            let arrayBuffer = null;
            let uploadResponseData = null;
            let fileUri = null;
            let mimeType = file ? file.type : null;

            if (file) {
                // We need an array buffer to upload natively
                arrayBuffer = await file.arrayBuffer();
            }

            // If we have an API key and a file, we upload directly from Browser
            if (apiKey && file) {
                console.log("Starting Browser-Direct Upload to Gemini...");
                const uploadRes = await fetch(`https://generativelanguage.googleapis.com/upload/v1beta/files?uploadType=media&key=${apiKey}`, {
                    method: 'POST',
                    headers: { 'X-Goog-Upload-Command': 'start, upload, finalize', 'X-Goog-Upload-Header-Content-Length': file.size.toString(), 'X-Goog-Upload-Header-Content-Type': file.type, 'Content-Type': file.type },
                    body: arrayBuffer
                });

                if (!uploadRes.ok) {
                    const err = await uploadRes.json();
                    throw new Error(`Direct upload failed: ${err.error?.message || uploadRes.statusText}`);
                }
                uploadResponseData = await uploadRes.json();
                fileUri = uploadResponseData.file.uri;
                console.log("Browser-Direct Upload Success! URI:", fileUri);
            } 

            // STEP 2: Send the File URI (or the file itself if no key) to our Backend
            const formData = new FormData();
            formData.append('subject', subjectInput.value.trim());
            if (subjectDetailsInput) {
                formData.append('subject_details', subjectDetailsInput.value.trim());
            }
            
            if (fileUri) {
                // If direct upload succeeded, just send the URI and metadata
                formData.append('file_uri', fileUri);
                formData.append('mime_type', mimeType);
                formData.append('filename', file.name);
            } else if (file) {
                 // Fallback to Vercel native upload (will fail if > 4.5MB)
                 formData.append('file', file);
            }

            const headers = getApiHeaders();
            const response = await fetch('/api/upload', {
                method: 'POST',
                headers: headers,
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                if (response.status === 429) {
                    throw new Error("⏳ Rate limit reached — try again in ~1 minute, or switch to Fast mode.");
                }
                throw new Error(data.error || 'Failed to analyze file');
            }

            if (!data.success) {
                throw new Error(data.error || 'Failed to analyze file');
            }

            if (window.gemini) {
               window.gemini._trackUsage(window.gemini.selectedModel);
            } else {
               trackUsage(getApiHeaders()['X-Gemini-Model-Name'] || 'gemini-2.5-pro');
            }

            // Update state
            state.subject = subjectInput.value.trim();
            if (subjectDetailsInput) {
                 state.subjectDetails = subjectDetailsInput.value.trim();
            }
            state.topics = data.topics || [];
            state.selectedTopics = [...state.topics]; // Initially select all
            state.fileName = data.filename || (file ? file.name : "No file attached"); 
            state.fileUri = data.file_uri || fileUri; // Store the URI for later question generation
            state.mimeType = data.mime_type || mimeType;

            // Update content preview
            contentPreview.textContent = data.content_preview || "Content analyzed successfully.";

            // Render topics in step 2
            renderTopics();

            // Navigate to step 2
            navigateToStep(2);

        } catch (error) {
            console.error("Analyze error:", error);
            showToast('Error', error.message);
        } finally {
            hideProgress();
        }
    }

    // Topic Selection
    function renderTopics() {
        topicsContainer.innerHTML = '';

        if (state.topics.length === 0) {
            topicsContainer.innerHTML = '<p class="text-muted">No topics identified. You can proceed with general questions.</p>';
            return;
        }

        state.topics.forEach(topic => {
            const isSelected = state.selectedTopics.some(t => t.topic === topic.topic);
            const topicElement = document.createElement('div');
            topicElement.className = `topic-badge ${isSelected ? 'selected' : ''}`;
            topicElement.textContent = topic.topic;
            topicElement.dataset.topic = topic.topic;

            topicElement.addEventListener('click', () => toggleTopic(topic));

            topicsContainer.appendChild(topicElement);
        });
    }

    function toggleTopic(topic) {
        const index = state.selectedTopics.findIndex(t => t.topic === topic.topic);

        if (index === -1) {
            // Topic not selected, add it
            state.selectedTopics.push(topic);
        } else {
            // Topic already selected, remove it
            state.selectedTopics.splice(index, 1);
        }

        // Update UI
        renderTopics();
    }

    function selectAllTopics() {
        state.selectedTopics = [...state.topics];
        renderTopics();
    }

    function deselectAllTopics() {
        state.selectedTopics = [];
        renderTopics();
    }

    // Question Generation
    async function handleGenerateQuestions() {
        // Validate inputs
        const numQuestions = parseInt(document.getElementById('num-questions').value);

        if (isNaN(numQuestions) || numQuestions < 1) {
            showToast('Error', 'Please enter a valid number of questions.');
            return;
        }

        const questionTypeCheckboxes = document.querySelectorAll('.question-type-check:checked');
        if (questionTypeCheckboxes.length === 0) {
            showToast('Error', 'Please select at least one question type.');
            return;
        }

        if (!state.subject) {
            showToast('Error', 'No subject available. Please provide a subject first.');
            navigateToStep(1);
            return;
        }

        showProgress();
        console.log("Generating questions with filename:", state.fileName);

        // --- UI/UX Mandate: Show Skeleton Loader ---
        const skeletonContainer = document.getElementById('skeleton-container');
        skeletonContainer.classList.remove('d-none');
        questionsContainer.innerHTML = ''; // Clear previous questions and hide empty state
        
        // Navigate to Step 3 early so the user sees the skeleton loading state
        navigateToStep(3);

        // Get parameter values
        const difficulty = document.getElementById('difficulty-select').value;
        const questionTypes = Array.from(questionTypeCheckboxes).map(cb => cb.value);
        const topics = state.selectedTopics.map(t => t.topic);

        try {
            const requestData = {
                filename: state.fileName,
                file_uri: state.fileUri || null,
                mime_type: state.mimeType || null,
                subject: state.subject,
                subject_details: state.subjectDetails || '',
                topics: topics,
                difficulty: difficulty,
                question_types: questionTypes,
                num_questions: numQuestions,
                question_bank: state.questionBank
            };

            console.log("Sending request with data:", requestData);

            const response = await fetch('/api/generate-questions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...getApiHeaders()
                },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                if (response.status === 429) {
                    throw new Error("⏳ Rate limit reached — try again in ~1 minute, or switch to Fast mode.");
                }
                const errorText = await response.text();
                throw new Error(`Server error (${response.status}): ${errorText}`);
            }

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to generate questions');
            }

            trackUsage(requestData.model_name || getApiHeaders()['X-Gemini-Model-Name'] || 'gemini-2.5-pro');

            // Update state
            state.generatedQuestions = data.questions;

            // Populate default exam title if empty
            if (!examTitleInput.value) {
                examTitleInput.value = `${state.subject} Exam - ${new Date().toLocaleDateString()}`;
            }

            // Render questions
            renderQuestions();

        } catch (error) {
            showToast('Error', error.message);
            // Hide skeleton on error so they aren't stuck on loading UI
            document.getElementById('skeleton-container').classList.add('d-none');
        } finally {
            hideProgress();
        }
    }

    function renderQuestions() {
        // --- UI/UX Mandate: Hide Skeleton Loader ---
        const skeletonContainer = document.getElementById('skeleton-container');
        skeletonContainer.classList.add('d-none');

        questionsContainer.innerHTML = '';

        if (state.generatedQuestions.length === 0) {
            questionsContainer.innerHTML = '<p class="text-center text-muted">No questions generated. Please try different parameters.</p>';
            return;
        }

        // Group questions by topic
        const questionsByTopic = {};
        state.generatedQuestions.forEach(question => {
            const topic = question.topic || 'General';
            if (!questionsByTopic[topic]) {
                questionsByTopic[topic] = [];
            }
            questionsByTopic[topic].push(question);
        });

        // Render questions by topic
        Object.entries(questionsByTopic).forEach(([topic, questions]) => {
            const topicElement = document.createElement('div');
            topicElement.className = 'mb-4';

            const topicHeader = document.createElement('h4');
            topicHeader.className = 'mb-3';
            topicHeader.textContent = topic;
            topicElement.appendChild(topicHeader);

            // Group by question type within topic
            const questionsByType = {};
            questions.forEach(question => {
                const type = question.type || 'Other';
                if (!questionsByType[type]) {
                    questionsByType[type] = [];
                }
                questionsByType[type].push(question);
            });

            // Render questions by type within topic
            Object.entries(questionsByType).forEach(([type, typeQuestions]) => {
                const typeElement = document.createElement('div');
                typeElement.className = 'mb-3';

                const typeHeader = document.createElement('h5');
                typeHeader.className = 'mb-3';
                typeHeader.textContent = `${type} Questions`;
                typeElement.appendChild(typeHeader);

                typeQuestions.forEach((question, index) => {
                    try {
                        const questionCard = createQuestionCard(question, index + 1);
                        typeElement.appendChild(questionCard);
                    } catch (error) {
                        console.error(`Error creating question card for question ${index}:`, error);
                        // Create a simpler fallback card
                        const fallbackCard = document.createElement('div');
                        fallbackCard.className = 'question-card';
                        fallbackCard.innerHTML = `<p class="text-danger">Error displaying question ${index + 1}.</p>`;
                        typeElement.appendChild(fallbackCard);
                    }
                });

                topicElement.appendChild(typeElement);
            });

            questionsContainer.appendChild(topicElement);
        });

        // Make sure all questions are visible regardless of answer toggle state
        document.querySelectorAll('.question-card').forEach(card => {
            card.style.display = 'block';
        });

        // Apply current answer visibility setting
        updateAnswerVisibility();
    }

    function createQuestionCard(question, index) {
        const card = document.createElement('div');
        card.className = 'question-card';
        card.dataset.id = question.id;

        // Header with type and difficulty
        const header = document.createElement('div');
        header.className = 'question-header';

        const questionNumber = document.createElement('span');
        questionNumber.className = 'question-number';
        questionNumber.textContent = `Question ${index}`;

        const infoContainer = document.createElement('div');

        const questionType = document.createElement('span');
        questionType.className = 'question-type';
        questionType.textContent = question.type || 'General';

        const difficultyBadge = document.createElement('span');
        difficultyBadge.className = `ms-2 difficulty-badge difficulty-${question.difficulty.toLowerCase()}`;
        difficultyBadge.textContent = question.difficulty || 'Medium';

        infoContainer.appendChild(questionType);
        infoContainer.appendChild(difficultyBadge);

        header.appendChild(questionNumber);
        header.appendChild(infoContainer);

        // Question text
        const questionText = document.createElement('p');
        questionText.className = 'mt-3 mb-3';
        questionText.textContent = question.text;

        card.appendChild(header);
        card.appendChild(questionText);

        // Add options for MCQs
        if (question.type === 'MCQ' && Array.isArray(question.options)) {
            const optionsContainer = document.createElement('div');
            optionsContainer.className = 'options-container';

            question.options.forEach((option, i) => {
                const optionElement = document.createElement('div');
                optionElement.className = 'question-option';

                const optionInput = document.createElement('input');
                optionInput.type = 'radio';
                optionInput.name = `question_${question.id}`;
                optionInput.id = `question_${question.id}_option_${i}`;
                optionInput.value = option;

                const optionLabel = document.createElement('label');
                optionLabel.htmlFor = `question_${question.id}_option_${i}`;
                optionLabel.textContent = option;

                optionElement.appendChild(optionInput);
                optionElement.appendChild(optionLabel);

                optionsContainer.appendChild(optionElement);
            });

            card.appendChild(optionsContainer);
        }

        // Add answer section (initially hidden)
        if (question.correct_answer) {
            const answerContainer = document.createElement('div');
            answerContainer.className = 'answer-container mt-3 pt-3 border-top d-none answer-section';

            const answerLabel = document.createElement('p');
            answerLabel.className = 'mb-1 fw-bold';
            answerLabel.textContent = 'Answer:';

            const answerText = document.createElement('p');
            answerText.textContent = question.correct_answer;

            answerContainer.appendChild(answerLabel);
            answerContainer.appendChild(answerText);

            if (question.explanation) {
                const explanationLabel = document.createElement('p');
                explanationLabel.className = 'mb-1 mt-2 fw-bold';
                explanationLabel.textContent = 'Explanation:';

                const explanationText = document.createElement('p');
                explanationText.className = 'fst-italic';
                explanationText.textContent = question.explanation;

                answerContainer.appendChild(explanationLabel);
                answerContainer.appendChild(explanationText);
            }

            card.appendChild(answerContainer);
        }

        return card;
    }

    // Exporting
    async function exportPaper(format) {
        if (state.generatedQuestions.length === 0) {
            showToast('Error', 'No questions to export. Please generate questions first.');
            return;
        }

        const title = examTitleInput.value.trim() || `${state.subject} Exam`;
        const includeAnswers = includeAnswersCheck.checked;

        showProgress();

        try {
            // Create a Blob object for the file download
            const questionsData = JSON.stringify(state.generatedQuestions);

            // Create form data for multipart/form-data submission
            const formData = new FormData();
            formData.append('questions', questionsData);
            formData.append('format', format);
            formData.append('title', title);
            formData.append('include_answers', includeAnswers.toString());

            // Use fetch with normal POST request
            const response = await fetch('/api/export', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Export failed with status: ${response.status}`);
            }

            // Get the blob from the response
            const blob = await response.blob();

            // Create a downloadable URL
            const url = window.URL.createObjectURL(blob);

            // Create a temporary link and click it to download
            const a = document.createElement('a');
            a.href = url;

            // Try to get filename from Content-Disposition header, fallback to default
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `${title.replace(/\s+/g, '_')}.${format}`;

            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1];
                }
            }

            a.download = filename;
            document.body.appendChild(a);
            a.click();

            // Clean up
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showToast('Success', `Exam paper exported as ${format.toUpperCase()}`);

        } catch (error) {
            console.error('Export error:', error);
            showToast('Error', `Failed to export paper: ${error.message}`);
        } finally {
            hideProgress();
        }
    }

    // Navigation
    function navigateToStep(step) {
        state.currentStep = step;

        // Hide all step content
        step1Content.classList.add('d-none');
        step2Content.classList.add('d-none');
        step3Content.classList.add('d-none');

        // Reset step indicators
        step1Dot.classList.remove('step-active', 'step-completed');
        step2Dot.classList.remove('step-active', 'step-completed');
        step3Dot.classList.remove('step-active', 'step-completed');

        // Show current step content and update indicators
        if (step === 1) {
            step1Content.classList.remove('d-none');
            step1Dot.classList.add('step-active');
        } else if (step === 2) {
            step2Content.classList.remove('d-none');
            step1Dot.classList.add('step-completed');
            step2Dot.classList.add('step-active');
        } else if (step === 3) {
            step3Content.classList.remove('d-none');
            step1Dot.classList.add('step-completed');
            step2Dot.classList.add('step-completed');
            step3Dot.classList.add('step-active');

            // Toggle answer visibility based on checkbox
            updateAnswerVisibility();
        }
    }

    // Update answer visibility when checkbox changes
    includeAnswersCheck.addEventListener('change', updateAnswerVisibility);

    function updateAnswerVisibility() {
        const answerSections = document.querySelectorAll('.answer-section');
        if (includeAnswersCheck.checked) {
            answerSections.forEach(section => section.classList.remove('d-none'));
        } else {
            answerSections.forEach(section => section.classList.add('d-none'));
        }

        // Important: Don't hide the questions themselves
        document.querySelectorAll('.question-card').forEach(card => {
            card.style.display = 'block';
        });
    }

    // Utility Functions
    function showToast(title, message) {
        toastTitle.textContent = title;
        toastMessage.textContent = message;
        bsToast.show();
    }

    function showProgress() {
        progressBar.style.width = '90%';
    }

    function hideProgress() {
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.style.width = '0%';
        }, 300);
    }
});