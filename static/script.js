document.addEventListener('DOMContentLoaded', function() {
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('fileElem');
    const conversionStatus = document.getElementById('conversionStatus');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');
    const downloadContainer = document.getElementById('downloadContainer');
    const downloadLink = document.getElementById('downloadLink');
    const fileInfo = document.getElementById('fileInfo');
    const errorContainer = document.getElementById('errorContainer');
    const errorMessage = document.getElementById('errorMessage');
    const retryButton = document.getElementById('retryButton');
    const cancelButton = document.getElementById('cancelButton');
    const reloadButton = document.getElementById('reloadButton');
    const reloadFooter = document.getElementById('reloadFooter');

    let currentTaskId = null;
    let statusCheckInterval = null;

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop area when item is dragged over
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });

    // Remove highlight when item is dragged away
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropArea.addEventListener('drop', handleDrop, false);
    
    // Handle clicked file input
    fileInput.addEventListener('change', handleFiles, false);
    
    // Handle the drop area click
    dropArea.addEventListener('click', () => fileInput.click(), false);
    
    // Handle retry button
    retryButton.addEventListener('click', resetUI, false);
    
    // Handle cancel button
    cancelButton.addEventListener('click', cancelConversion, false);
    
    // Handle reload buttons
    reloadButton.addEventListener('click', resetUI, false);
    reloadFooter.addEventListener('click', function(e) {
        e.preventDefault();
        resetUI();
    }, false);

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight() {
        dropArea.classList.add('highlight');
    }

    function unhighlight() {
        dropArea.classList.remove('highlight');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles({ target: { files: files } });
    }

    function resetUI() {
        // Reset all containers
        dropArea.style.display = 'flex';
        conversionStatus.style.display = 'none';
        downloadContainer.style.display = 'none';
        errorContainer.style.display = 'none';
        
        // Reset progress
        progressBar.style.width = '0%';
        
        // Reset file input
        fileInput.value = '';
        
        // Clear task ID
        currentTaskId = null;
        
        // Clear interval
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
        
        // Add a small animation to the drop area
        dropArea.classList.add('reset-animation');
        setTimeout(() => {
            dropArea.classList.remove('reset-animation');
        }, 500);
    }
    
    function cancelConversion() {
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
            statusCheckInterval = null;
        }
        resetUI();
    }

    function handleFiles(e) {
        let files;
        if (e.dataTransfer) {
            files = e.dataTransfer.files;
        } else {
            files = e.target.files;
        }
        
        if (!files || files.length === 0) {
            showError("Please select a file.");
            return;
        }
        
        const file = files[0];
        const validTypes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/mp3'];
        const fileExtension = file.name.split('.').pop().toLowerCase();
        const validExtensions = ['mp3', 'wav'];
        
        // Check if file type is valid
        let isValid = false;
        
        // Check MIME type first
        if (validTypes.includes(file.type)) {
            isValid = true;
        } 
        // If MIME type check fails, check extension
        else if (validExtensions.includes(fileExtension)) {
            isValid = true;
        }
        
        if (!isValid) {
            showError("Only MP3 or WAV files are allowed.");
            return;
        }
        
        // File size check (100MB max)
        if (file.size > 100 * 1024 * 1024) {
            showError("File size exceeds 100MB limit.");
            return;
        }
        
        // Check if file is not empty
        if (file.size === 0) {
            showError("The file is empty.");
            return;
        }
        
        uploadFile(file);
    }
    
    function showError(message) {
        errorMessage.textContent = message;
        dropArea.style.display = 'none';
        conversionStatus.style.display = 'none';
        downloadContainer.style.display = 'none';
        errorContainer.style.display = 'block';
    }

    // Helper function to format file size
    function formatFileSize(bytes) {
        if (!bytes) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function uploadFile(file) {
        // Show conversion status with 0% progress
        dropArea.style.display = 'none';
        errorContainer.style.display = 'none';
        downloadContainer.style.display = 'none';
        conversionStatus.style.display = 'block';
        progressBar.style.width = '0%';
        statusMessage.textContent = 'Uploading file...';
        
        const formData = new FormData();
        formData.append('audiofile', file);
        
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(data => {
                    throw new Error(data.error || `HTTP error! Status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            if (data.task_id) {
                currentTaskId = data.task_id;
                statusMessage.textContent = 'Converting...';
                progressBar.style.width = '10%';
                
                // Start checking status
                checkConversionStatus();
            } else {
                throw new Error('No task ID returned from server');
            }
        })
        .catch(error => {
            console.error('Upload error:', error);
            showError(`Upload failed: ${error.message}`);
        });
    }

    function checkConversionStatus() {
        if (!currentTaskId) return;
        
        // Check status every 1 second
        statusCheckInterval = setInterval(() => {
            fetch(`/status/${currentTaskId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.status === 'unknown') {
                        clearInterval(statusCheckInterval);
                        showError('Conversion task not found');
                        return;
                    }
                    
                    if (data.status === 'error') {
                        clearInterval(statusCheckInterval);
                        showError(`Conversion failed: ${data.error || 'Unknown error'}`);
                        return;
                    }
                    
                    if (data.status === 'processing') {
                        progressBar.style.width = `${data.progress || 0}%`;
                        statusMessage.textContent = `Converting... ${data.progress || 0}%`;
                    }
                    
                    if (data.status === 'complete') {
                        clearInterval(statusCheckInterval);
                        progressBar.style.width = '100%';
                        
                        // Show download option
                        conversionStatus.style.display = 'none';
                        downloadContainer.style.display = 'block';
                        
                        // Set download link
                        downloadLink.href = `/download/${currentTaskId}`;
                        
                        // Show file info
                        const originalFormat = data.original_format || {};
                        fileInfo.innerHTML = `
                            <p><strong>Filename:</strong> ${data.filename || 'converted_audio.wav'}</p>
                            <p><strong>Original:</strong> ${formatFileSize(data.original_size)} - 
                                ${originalFormat.channels || '?'} channel(s), 
                                ${originalFormat.sample_rate || '?'} Hz, 
                                ${originalFormat.bit_depth || '?'} bit</p>
                            <p><strong>Converted:</strong> ${formatFileSize(data.converted_size)} - 
                                1 channel, 8000 Hz, 16 bit</p>
                        `;
                        
                        // Add a click event to the download link to track successful downloads
                        downloadLink.addEventListener('click', function() {
                            // Optional: Track successful downloads or analytics here
                            console.log('Download initiated for task:', currentTaskId);
                        }, { once: true });
                    }
                })
                .catch(error => {
                    console.error('Status check error:', error);
                    clearInterval(statusCheckInterval);
                    showError(`Error checking status: ${error.message}`);
                });
        }, 1000);
    }
});