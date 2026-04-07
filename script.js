document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const ocrLoader = document.getElementById('ocrLoader');
    const ocrSuccess = document.getElementById('ocrSuccess');
    const previewContainer = document.getElementById('previewContainer');
    const studentForm = document.getElementById('studentForm');

    // --- Drag and Drop Logic ---
    dropZone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        handleFileUpload(file);
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        handleFileUpload(file);
    });

    function handleFileUpload(file) {
        if (!file) return;

        // Reset status
        ocrSuccess.style.display = 'none';
        ocrLoader.style.display = 'flex';
        previewContainer.innerHTML = '';

        // Mocking OCR Process
        setTimeout(() => {
            simulateOCR();
        }, 3000);
    }

    function simulateOCR() {
        ocrLoader.style.display = 'none';
        ocrSuccess.style.display = 'block';

        // Auto-fill form with mock data
        document.getElementById('nev').value = 'Molnár Ákos';
        document.getElementById('email').value = 'molnar.akos@pelda.hu';
        document.getElementById('telefon').value = '+36 30 555 1234';
        document.getElementById('lakhely').value = 'Budapest, 1051 Deák Ferenc tér 1.';
        document.getElementById('tagozat').value = 'nappali';
        document.getElementById('osztaly').value = '12.C';
        document.getElementById('szerzodes_kezdet').value = '2024-09-01';
        document.getElementById('szerzodes_vege').value = '2027-06-15';

        // Add some metadata tags
        addMetadataTag('allergia', 'tejtermék');
        addMetadataTag('diákigazolvány', '848322DA');
    }

    // --- Metadata Logic ---
    const metaKey = document.getElementById('metaKey');
    const metaValue = document.getElementById('metaValue');
    const addMetaBtn = document.getElementById('addMeta');
    const metadataTags = document.getElementById('metadataTags');
    const metadataStore = {};

    addMetaBtn.addEventListener('click', () => {
        const key = metaKey.value.trim();
        const value = metaValue.value.trim();

        if (key && value) {
            addMetadataTag(key, value);
            metaKey.value = '';
            metaValue.value = '';
        }
    });

    function addMetadataTag(key, value) {
        if (metadataStore[key]) return; // Simple duplication check

        metadataStore[key] = value;
        const tag = document.createElement('div');
        tag.className = 'tag';
        tag.innerHTML = `
            <span><strong>${key}:</strong> ${value}</span>
            <i class="fas fa-times" data-key="${key}"></i>
        `;

        tag.querySelector('i').addEventListener('click', (e) => {
            const k = e.target.getAttribute('data-key');
            delete metadataStore[k];
            tag.remove();
        });

        metadataTags.appendChild(tag);
    }

    // --- Form Submission ---
    studentForm.addEventListener('submit', (e) => {
        e.preventDefault();

        // Check date validation (requested in previous step)
        const start = new Date(document.getElementById('szerzodes_kezdet').value);
        const end = new Date(document.getElementById('szerzodes_vege').value);

        if (end < start) {
            alert('Hiba: A szerződés vége nem lehet korábbi a kezdeténél!');
            return;
        }

        const formData = {
            nev: document.getElementById('nev').value,
            email: document.getElementById('email').value,
            metadata: metadataStore
        };

        console.log('Mentett adatok:', formData);
        
        // Show success animation/alert
        alert('Diák adatai sikeresen rögzítve az adatbázisban!');
    });
});
