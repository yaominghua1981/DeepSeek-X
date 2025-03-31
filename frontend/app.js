let config = {};
let corsSources = [];
let authToken = '';  // Store authentication token

// Initialize system
document.addEventListener("DOMContentLoaded", () => {
    // Check if token exists in local storage
    authToken = localStorage.getItem('authToken');
    if (authToken) {
        // If token exists, try to load configuration automatically
        loadConfigToUI().then(success => {
            if (success) {
                hideAllScreens();
                document.getElementById("config").style.display = "block";
                // Initialize workflow settings
                loadWorkflowSettings();
            } else {
                // If loading fails, clear token and show login screen
                localStorage.removeItem('authToken');
                authToken = '';
                showLogin();
            }
        });
    } else {
        // If no token, show welcome screen
        showWelcome();
    }

    // 为系统设置添加事件监听器
    document.getElementById("log-level").addEventListener("change", collectAllData);
    document.getElementById("api-key").addEventListener("change", collectAllData);
    document.getElementById("request-timeout").addEventListener("change", collectAllData);
    document.getElementById("proxy-address").addEventListener("change", collectAllData);
    document.getElementById("proxy-toggle").addEventListener("change", collectAllData);
});

/**********************
 *  File Operation Functions
 **********************/

// Add message display functions
let toastTimeout = null;
let toastQueue = [];
let isProcessingQueue = false;

function showToast(message, type = 'success') {
    // Create toast container if it doesn't exist
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="icon">${type === 'success' ? '✓' : '✕'}</span>
        <span class="message">${message}</span>
        <span class="close">×</span>
    `;

    // Add to container
    container.appendChild(toast);

    // Show toast
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Handle close button
    toast.querySelector('.close').addEventListener('click', () => {
        hideToast(toast);
    });

    // Clear any existing timeout
    if (toastTimeout) {
        clearTimeout(toastTimeout);
    }

    // Auto hide after 1 second
    toastTimeout = setTimeout(() => {
        hideToast(toast);
    }, 1000);
}

function hideToast(toast) {
    if (!toast) return;
    
    toast.classList.remove('show');
    setTimeout(() => {
        if (toast && toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 300);
}

async function saveConfig() {
    try {
        console.log("Starting to save configuration...");
        let response;
        try {
            // Try main endpoint
            response = await fetch('/api/config_save', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify(config)
            });
        } catch (fetchError) {
            console.error("Main endpoint error:", fetchError);
            throw fetchError;
        }
        
        const result = await response.json();
        if (result.success) {
            console.log("Configuration saved successfully");
            showSuccess("Configuration saved successfully!");
            return true;
        } else {
            console.error("Save failed:", result.error);
            showError("Save failed: " + (result.error || "Unknown error"));
            return false;
        }
    } catch (error) {
        console.error("Save request failed:", error);
        showError("Failed to connect to server");
        return false;
    }
}

/**********************
 *  UI Control Functions
 **********************/ 
function hideAllScreens() {
    document.getElementById("welcome").style.display = "none";
    document.getElementById("login").style.display = "none";
    document.getElementById("config").style.display = "none";
}

function showWelcome() {
    const mainContent = document.getElementById('main-content');
    mainContent.innerHTML = `
        <div class="welcome-container">
            <h1>Welcome to DeepSeek-X</h1>
            <p>Please select a configuration option from the sidebar.</p>
        </div>
    `;
}

function showLogin() {
    hideAllScreens();
    document.getElementById("login").style.display = "flex";
}

function showMainUI() {
    hideAllScreens();
    document.getElementById("config").style.display = "block";
    // Initialize workflow settings when showing main UI
    loadWorkflowSettings();
}

function switchTab(tabName) {
    // Tab switching logic
    document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(content => content.classList.remove("active"));
    
    // Add active class to selected tab
    const selectedTab = document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`);
    if (selectedTab) {
        selectedTab.classList.add("active");
    }
    
    // Show selected content
    const selectedContent = document.getElementById(tabName);
    if (selectedContent) {
        selectedContent.classList.add("active");
        
        // Load data for specific tabs
        if (tabName === 'inference') {
            loadInferenceModels();
        } else if (tabName === 'target') {
            loadTargetModels();
        } else if (tabName === 'composite') {
            loadCompositeModels();
        } else if (tabName === 'proxy') {
            loadProxySettings();
        } else if (tabName === 'system') {
            loadSystemSettings();
        } else if (tabName === 'workflow') {
            loadWorkflowSettings();
        }
    }
}

/**********************
 *  Configuration Data Management
 **********************/
async function loadConfigToUI() {
    try {
        console.log("Starting to load configuration...");
        
        // First, fetch the configuration from the server
        const response = await fetch('/api/config_get', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`Failed to fetch configuration: ${response.status} ${response.statusText}`);
        }
        
        const result = await response.json();
        console.log("Received configuration response:", result);
        
        if (!result.success) {
            throw new Error(result.error || "Failed to load configuration");
        }
        
        // Update the config object with the fetched data
        config = result.config || {};
        console.log("Configuration loaded successfully:", config);

        // Load system settings
        const systemConfig = config.system || {};
        console.log("Loading system settings:", systemConfig);
        document.getElementById("log-level").value = systemConfig.logLevel || "INFO";
        document.getElementById("api-key").value = systemConfig.apiKey || "";
        document.getElementById("request-timeout").value = systemConfig.requestTimeout || 60000;

        // Load CORS settings
        corsSources = systemConfig.cors || [];
        console.log("Loading CORS settings:", corsSources);
        updateCorsList();

        // Load proxy settings
        const proxyConfig = config.proxy || {};
        console.log("Loading proxy settings:", proxyConfig);
        document.getElementById("proxy-address").value = (proxyConfig.address || "").replace(/^https?:\/\//, '');
        document.getElementById("proxy-toggle").checked = proxyConfig.enabled || false;

        // Load model data with null checks
        console.log("Loading model data:", {
            inference: config.inference || {},
            target: config.target || {},
            composite: config.composite || {}
        });
        loadModelSection("inference", config.inference || {});
        loadModelSection("target", config.target || {});
        loadModelSection("composite", config.composite || {});
        
        // Load workflow settings
        console.log("Loading workflow settings:", config.workflow || {});
        await loadWorkflowSettings();
        
        // Update composite model dropdowns
        updateCompositeModelDropdowns();
        
        // Initialize model selector hover info
        setTimeout(initializeModelSelects, 500);
        
        console.log("UI updated successfully with configuration");
        return true;
    } catch (error) {
        console.error("Configuration loading failed:", error);
        alert("Failed to load configuration: " + error.message);
        
        // Set default configuration
        config = {
            composite: {},
            inference: {},
            target: {},
            proxy: { address: "", enabled: false },
            system: { cors: [], logLevel: "INFO", apiKey: "", requestTimeout: 60000 },
            workflow: {
                phase1_inference: {
                    step: [
                        { stream: true, retry_num: 0 },
                        { stream: false, retry_num: 0 }
                    ]
                },
                phase2_final: {
                    step: [
                        { stream: true, retry_num: 0 },
                        { stream: false, retry_num: 0 }
                    ]
                }
            }
        };
        
        return false;
    }
}

async function collectAllData() {
    try {
        // Collect system settings
        config.system = {
            cors: corsSources,
            logLevel: document.getElementById("log-level").value,
            apiKey: document.getElementById("api-key").value,
            requestTimeout: parseInt(document.getElementById("request-timeout").value) || 60000
        };
        
        // Collect proxy settings
        config.proxy = {
            address: document.getElementById("proxy-address").value.trim(),
            enabled: document.getElementById("proxy-toggle").checked
        };
        
        // Collect model data
        config.composite = collectModelData("composite");
        config.inference = collectModelData("inference");
        config.target = collectModelData("target");
        
        // Collect workflow settings
        config.workflow = {
            phase1_inference: {
                step: collectWorkflowSteps('inference-steps')
            },
            phase2_final: {
                step: collectWorkflowSteps('final-steps')
            }
        };
        
        // Save configuration immediately
        return await saveConfig();
    } catch (error) {
        console.error('Error collecting data:', error);
        showError('Failed to save configuration');
        return false;
    }
}

function getModelFields(type) {
    if (type === "composite") {
        return ["Model ID", "Inference Model", "Target Model"]; // Changed field display order
    } else if (type === "inference" || type === "target") {
        return ["Model ID", "API Key", "Base URL", "API Path", "Model Type"];
    }
    return [];
}

function collectModelData(type) {
    const container = document.getElementById(`${type}-models`);
    const models = {};
    
    if (!container) return models;
    
    container.querySelectorAll('.model-section').forEach(section => {
        const aliasInput = section.querySelector('.model-alias');
        const alias = aliasInput ? aliasInput.value.trim() : '';
        
        if (!alias) return; // Skip models without alias
        
        // Create model data object
        const modelData = {};
        
        // Get required fields based on type
        const displayFields = getModelFields(type);
        const allFields = type === 'composite' ? [...displayFields, 'activated'] : displayFields;
        
        // Collect values for each field
        allFields.forEach(field => {
            // Special handling for composite model fields
            if (type === 'composite') {
                if (field === 'Inference Model' || field === 'Target Model') {
                    const select = section.querySelector(`select[data-model-type="${field === 'Inference Model' ? 'inference' : 'target'}"]`);
                    modelData[field] = select ? select.value : '';
                } else if (field === 'activated') {
                    // Get activation status
                    const activateCheckbox = section.querySelector('.model-activate-checkbox');
                    modelData[field] = activateCheckbox ? activateCheckbox.checked : false;
                } else {
                    const input = section.querySelector(`input[placeholder="${field}"]`);
                    modelData[field] = input ? input.value.trim() : '';
                }
            } else {
                // Regular model field collection
                const input = section.querySelector(`input[placeholder="${field}"]`);
                modelData[field] = input ? input.value.trim() : '';
            }
        });
        
        // Add to result set
        models[alias] = modelData;
    });
    
    return models;
}

function generateDefaultAlias(type) {
    const prefix = type === 'composite' ? 'Composite Model' : 
                   type === 'inference' ? 'Inference Model' : 
                   type === 'target' ? 'Target Model' : type;
    const count = Object.keys(config[type] || {}).length + 1;
    return `${prefix}${count}`;
}

/**********************
 *  Model Management Functions
 **********************/
function addModel(type) {
    const container = document.getElementById(`${type}-models`);
    if (!container) {
        console.error(`${type} models container not found`);
        return;
    }
    
    const modelId = generateId();
    const modelSection = document.createElement('div');
    modelSection.className = 'model-section';
    
    if (type === 'composite') {
        const html = `
        <div class="model-section" id="${modelId}">
            <div class="model-header">
                <input 
                    type="text" 
                    placeholder="Model Alias"
                    class="model-alias" 
                    value="${generateDefaultAlias(type)}"
                    onchange="collectAllData()"
                >
                <div class="model-actions">
                    <button onclick="deleteModel('${modelId}')">Delete</button>
                </div>
            </div>
            <div class="model-content">
                <div class="field-group">
                    <label>Model ID:</label>
                    <input type="text" placeholder="Model ID" onchange="collectAllData()">
                </div>
                <div class="field-group">
                    <label>Inference Model:</label>
                    <select class="model-select" onchange="collectAllData()">
                        <option value="">Select Inference Model</option>
                    </select>
                </div>
                <div class="field-group">
                    <label>Target Model:</label>
                    <select class="model-select" onchange="collectAllData()">
                        <option value="">Select Target Model</option>
                    </select>
                </div>
                <div class="field-group">
                    <label class="switch-label">Activated:</label>
                    <label class="toggle-switch">
                        <input type="checkbox" onchange="collectAllData()">
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
        </div>
        `;
        modelSection.innerHTML = html;
    } else {
        // Use original template for other model types
        const html = `
        <div class="model-section" id="${modelId}">
            <div class="model-header">
                <input 
                    type="text" 
                    placeholder="Model Alias"
                    class="model-alias" 
                    value="${generateDefaultAlias(type)}"
                    onchange="collectAllData()"
                >
                <div class="model-actions">
                    <button onclick="deleteModel('${modelId}')">Delete</button>
                </div>
            </div>
            <div class="model-content">
                ${getModelFields(type).map(f => `
                    <div class="field-group">
                        <label>${f}:</label>
                        <input 
                            type="${f === 'API Key' ? 'password' : 'text'}" 
                            placeholder="${f}"
                            class="${f === 'API Key' ? 'api-key-field' : ''}" 
                            onchange="collectAllData()"
                        >
                    </div>
                `).join("")}
            </div>
        </div>
        `;
        modelSection.innerHTML = html;
    }
    
    container.appendChild(modelSection);
    // Save configuration immediately
    collectAllData();
}

function loadModelSection(type, data) {
    const container = document.getElementById(`${type}-models`);
    if (!container) {
        console.error(`[${type}] Target container not found`);
        return;
    }
    try {
        // Convert object data to HTML
        const modelEntries = Object.entries(data);
        if (!modelEntries.length) {
            container.innerHTML = ''; // Empty model list
            return;
        }
        
        container.innerHTML = modelEntries.map(([alias, model]) => {
            if (!model || typeof model !== 'object' || Object.keys(model).length === 0) {
                console.warn('Invalid model data found', model);
                return '';
            }
            return createModelItem(type, model, alias);
        }).join('');
    } catch (error) {
        console.error(`[${type}] Error rendering models:`, error);
        container.innerHTML = `<div class="error">Configuration loading error, please check data format</div>`;
    }
} 

function createModelItem(type, model, alias) {
    const fields = getModelFields(type);
    const modelId = generateId();
    const safeModel = model || {}; // Prevent model from being null/undefined
    
    // Only add activation toggle for composite models
    const isComposite = type === 'composite';
    const isActivated = isComposite ? (safeModel['activated'] === true) : false;
    
    // Add activation toggle button (only for composite models)
    const activateToggle = isComposite ? `
        <label class="toggle-switch model-activate-toggle">
            <input type="checkbox" class="model-activate-checkbox" ${isActivated ? 'checked' : ''} 
                   onchange="toggleCompositeModelActivation('${modelId}', this.checked)">
            <span class="slider"></span>
        </label>
    ` : '';
    
    return `
        <div class="model-section ${isActivated ? 'model-activated' : ''}" id="${modelId}" data-model-alias="${alias || ''}">
            <div class="model-header">
                <input 
                    type="text" 
                    placeholder="Model Alias"
                    class="model-alias" 
                    value="${alias || ''}"
                    onchange="collectAllData()"
                >
                <div class="model-actions">
                    <button class="delete-btn" onclick="deleteModel('${modelId}')">Delete</button>
                    ${activateToggle}
                </div>
            </div>
            <div class="model-content">
                ${fields.map(f => `
                    <div class="field-group">
                        <label>${f}:</label>
                        ${createFieldInput(type, f, safeModel[f] || '')}
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function createFieldInput(type, fieldName, value) {
    // Create dropdown menus for specific fields in composite models
    if (type === 'composite') {
        if (fieldName === 'Inference Model') {
            return createModelSelect('inference', value);
        } else if (fieldName === 'Target Model') {
            return createModelSelect('target', value);
        }
    }
    
    // Use default input for other fields
    return `
        <input 
            type="${fieldName === 'API Key' ? 'password' : 'text'}"
            class="${fieldName === 'API Key' ? 'api-key-field' : ''}"
            placeholder="${fieldName}"
            value="${value || ''}"
            onchange="collectAllData()"
        >
    `;
}

function createModelSelect(modelType, selectedValue) {
    const models = config[modelType] || {};
    const options = Object.entries(models).map(([alias, model]) => {
        const modelId = model['Model ID'] || '';
        return `<option value="${alias}" data-model-id="${modelId}" ${alias === selectedValue ? 'selected' : ''}>${alias}</option>`;
    });
    
    return `
        <div class="select-wrapper">
            <select class="model-select" data-model-type="${modelType}" onchange="collectAllData(); updateModelInfoTooltip(this)">
                <option value="">-- Please Select --</option>
                ${options.join('')}
            </select>
            <div class="model-info-tooltip"></div>
        </div>
    `;
}

// Update composite model dropdown options
function updateCompositeModelDropdowns() {
    const compositeModels = document.querySelectorAll('#composite-models .model-section');
    compositeModels.forEach(model => {
        const inferenceSelect = model.querySelector('select[data-model-type="inference"]');
        const targetSelect = model.querySelector('select[data-model-type="target"]');
        
        if (inferenceSelect) {
            updateModelSelectOptions(inferenceSelect, 'inference');
        }
        
        if (targetSelect) {
            updateModelSelectOptions(targetSelect, 'target');
        }
    });
    
    // Initialize all select box info displays
    initializeModelSelects();
}

function updateModelSelectOptions(selectElement, modelType) {
    // Save current selected value
    const currentValue = selectElement.value;
    
    // Get all models
    const models = config[modelType] || {};
    
    // Build options
    let optionsHtml = '<option value="">-- Please Select --</option>';
    Object.entries(models).forEach(([alias, model]) => {
        const modelId = model['Model ID'] || '';
        optionsHtml += `<option value="${alias}" title="${modelId}" ${alias === currentValue ? 'selected' : ''}>${alias}</option>`;
    });
    
    // Update dropdown menu
    selectElement.innerHTML = optionsHtml;
}

// Toggle composite model activation status
function toggleCompositeModelActivation(modelId, isActivated) {
    const modelSection = document.getElementById(modelId);
    if (!modelSection) return;
    
    // Update UI status
    if (isActivated) {
        modelSection.classList.add('model-activated');
        
        // Deactivate all other composite models
        document.querySelectorAll('#composite-models .model-section').forEach(section => {
            if (section.id !== modelId) {
                section.classList.remove('model-activated');
                const checkbox = section.querySelector('.model-activate-checkbox');
                if (checkbox) checkbox.checked = false;
            }
        });
    } else {
        modelSection.classList.remove('model-activated');
    }
    
    // Save configuration immediately
    collectAllData();
}

// Update tooltip display function
function updateModelInfoTooltip(selectElement) {
    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const modelId = selectedOption.getAttribute('data-model-id');
    const tooltip = selectElement.parentNode.querySelector('.model-info-tooltip');
    
    if (modelId && selectedOption.value) {
        tooltip.textContent = `Model ID: ${modelId}`;
        tooltip.style.display = 'block';
    } else {
        tooltip.style.display = 'none';
    }
}

// Initialize all selectors' tooltips
function initializeModelSelects() {
    document.querySelectorAll('.model-select').forEach(select => {
        updateModelInfoTooltip(select);
        
        // Add mouse and focus events
        select.addEventListener('focus', function() {
            const tooltip = this.parentNode.querySelector('.model-info-tooltip');
            if (tooltip.textContent) {
                tooltip.classList.add('visible');
            }
        });
        
        select.addEventListener('blur', function() {
            const tooltip = this.parentNode.querySelector('.model-info-tooltip');
            tooltip.classList.remove('visible');
        });
        
        select.addEventListener('change', function() {
            updateModelInfoTooltip(this);
        });
    });
}

function updateModel(id) {
    const section = document.getElementById(id);
    const inputs = section.querySelectorAll("input");
    inputs.forEach(input => {
        const currentValue = input.value;
        input.value = ""; // Clear to simulate update process
        setTimeout(() => input.value = currentValue, 100); // Demonstrate update effect
    });
}

function deleteModel(modelId) {
    const modelSection = document.getElementById(modelId);
    if (modelSection) {
        modelSection.remove();
        // Save configuration immediately
        collectAllData();
    }
}

function generateId() {
    return Math.random().toString(36).substr(2, 9);
}

/**********************
 *  System Settings Functions
 **********************/
function addCorsSource() {
    const input = document.getElementById("cors-input");
    const source = input.value.trim();
    
    if (source && !corsSources.includes(source)) {
        corsSources.push(source);
        updateCorsList();
        input.value = '';
        // Save configuration immediately
        collectAllData();
    }
}

function updateCorsList() {
    const list = document.getElementById("cors-list");
    list.innerHTML = corsSources.map(source => `
        <div class="source-item">
            <span>${source}</span>
            <button onclick="removeCorsSource('${source}')">Delete</button>
        </div>
    `).join("");
}

function removeCorsSource(source) {
    corsSources = corsSources.filter(s => s !== source);
    updateCorsList();
    // Save configuration immediately
    collectAllData();
}

/**********************
 *  User Operation Entry Points
 **********************/
async function login() {
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: document.getElementById("token").value })
        });
        
        const result = await response.json();
        if (result.success) {
            // Save token for subsequent requests
            authToken = result.token;
            localStorage.setItem('authToken', authToken);
            
            // Load configuration after successful login
            const configSuccess = await loadConfigToUI();
            if (configSuccess) {
                hideAllScreens();
                document.getElementById("config").style.display = "block";
                // Initialize workflow settings after login
                loadWorkflowSettings();
            } else {
                alert("Login successful but failed to load configuration, please check server status");
            }
        } else {
            alert("Login failed: " + (result.error || "Unknown error"));
        }
    } catch (error) {
        console.error("Login request failed:", error);
        alert("Failed to connect to server");
    }
}

function logout() {
    // Clear token and return to welcome screen
    localStorage.removeItem('authToken');
    authToken = '';
    hideAllScreens();
    document.getElementById("welcome").style.display = "flex";
}

// Add new page content
function initializeWorkflowSettings() {
    const workflowContainer = document.getElementById('workflow');
    if (!workflowContainer) {
        console.error('Workflow settings container not found');
        return;
    }
    
    // Add default steps if none exist
    const inferenceContainer = document.getElementById('inference-steps');
    const finalContainer = document.getElementById('final-steps');
    
    if (inferenceContainer && inferenceContainer.children.length === 0) {
        addInferenceStep();
    }
    
    if (finalContainer && finalContainer.children.length === 0) {
        addFinalStep();
    }
}

// Add new functions
function addInferenceStep() {
    const container = document.getElementById('inference-steps');
    if (!container) {
        console.error('Inference steps container not found');
        return;
    }
    
    const stepDiv = document.createElement('div');
    stepDiv.className = 'step-item';
    stepDiv.innerHTML = `
        <div class="step-field">
            <label>Request:</label>
            <select class="step-type" onchange="collectAllData()">
                <option value="stream">Stream</option>
                <option value="non-stream">Non-Stream</option>
            </select>
        </div>
        <div class="step-field">
            <label>Retry:</label>
            <input type="number" class="retry-count" value="0" min="0" onchange="collectAllData()">
        </div>
        <button class="delete-btn" onclick="this.parentElement.remove(); collectAllData();">Delete</button>
    `;
    container.appendChild(stepDiv);
    // Save configuration immediately
    collectAllData();
}

function addFinalStep() {
    const container = document.getElementById('final-steps');
    if (!container) {
        console.error('Final steps container not found');
        return;
    }
    
    const stepDiv = document.createElement('div');
    stepDiv.className = 'step-item';
    stepDiv.innerHTML = `
        <div class="step-field">
            <label>Request:</label>
            <select class="step-type" onchange="collectAllData()">
                <option value="stream">Stream</option>
                <option value="non-stream">Non-Stream</option>
            </select>
        </div>
        <div class="step-field">
            <label>Retry:</label>
            <input type="number" class="retry-count" value="0" min="0" onchange="collectAllData()">
        </div>
        <button class="delete-btn" onclick="this.parentElement.remove(); collectAllData();">Delete</button>
    `;
    container.appendChild(stepDiv);
    // Save configuration immediately
    collectAllData();
}

async function loadWorkflowSettings() {
    try {
        // Get containers
        const inferenceContainer = document.getElementById('inference-steps');
        const finalContainer = document.getElementById('final-steps');
        
        if (!inferenceContainer || !finalContainer) {
            console.error('Workflow containers not found');
            return;
        }
        
        // Clear existing content
        inferenceContainer.innerHTML = '';
        finalContainer.innerHTML = '';
        
        // Load inference steps if they exist
        if (config.workflow && config.workflow.phase1_inference && config.workflow.phase1_inference.step && config.workflow.phase1_inference.step.length > 0) {
            config.workflow.phase1_inference.step.forEach(step => {
                const stepDiv = document.createElement('div');
                stepDiv.className = 'step-item';
                stepDiv.innerHTML = `
                    <div class="step-field">
                        <label>Request:</label>
                        <select class="step-type" onchange="collectAllData()">
                            <option value="stream" ${step.stream ? 'selected' : ''}>Stream</option>
                            <option value="non-stream" ${!step.stream ? 'selected' : ''}>Non-Stream</option>
                        </select>
                    </div>
                    <div class="step-field">
                        <label>Retry:</label>
                        <input type="number" class="retry-count" value="${step.retry_num || 0}" min="0" onchange="collectAllData()">
                    </div>
                    <button class="delete-btn" onclick="this.parentElement.remove(); collectAllData();">Delete</button>
                `;
                inferenceContainer.appendChild(stepDiv);
            });
        }
        
        // Load final steps
        if (config.workflow && config.workflow.phase2_final && config.workflow.phase2_final.step) {
            config.workflow.phase2_final.step.forEach(step => {
                const stepDiv = document.createElement('div');
                stepDiv.className = 'step-item';
                stepDiv.innerHTML = `
                    <div class="step-field">
                        <label>Request:</label>
                        <select class="step-type" onchange="collectAllData()">
                            <option value="stream" ${step.stream ? 'selected' : ''}>Stream</option>
                            <option value="non-stream" ${!step.stream ? 'selected' : ''}>Non-Stream</option>
                        </select>
                    </div>
                    <div class="step-field">
                        <label>Retry:</label>
                        <input type="number" class="retry-count" value="${step.retry_num || 0}" min="0" onchange="collectAllData()">
                    </div>
                    <button class="delete-btn" onclick="this.parentElement.remove(); collectAllData();">Delete</button>
                `;
                finalContainer.appendChild(stepDiv);
            });
        }

        // Add default steps if none exist
        if (inferenceContainer.children.length === 0) {
            addInferenceStep();
        }
        
        if (finalContainer.children.length === 0) {
            addFinalStep();
        }
    } catch (error) {
        console.error('Error loading workflow settings:', error);
        showError('Failed to load workflow settings');
    }
}

function collectWorkflowSteps(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return [];
    
    return Array.from(container.querySelectorAll('.step-item')).map(step => {
        const streamSelect = step.querySelector('.step-type');
        const retryInput = step.querySelector('.retry-count');
        
        return {
            stream: streamSelect.value === 'stream',
            retry_num: parseInt(retryInput.value) || 0
        };
    });
}

// Modify the showPage function to include the new page
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(page => {
        page.style.display = 'none';
    });
    
    // Show selected page
    const selectedPage = document.getElementById(pageId);
    if (selectedPage) {
        selectedPage.style.display = 'block';
        
        // Load data for specific pages
        if (pageId === 'inference-models') {
            loadInferenceModels();
        } else if (pageId === 'target-models') {
            loadTargetModels();
        } else if (pageId === 'composite-models') {
            loadCompositeModels();
        } else if (pageId === 'workflow-settings') {
            loadWorkflowSettings();
        }
    }
}

// Initialize all pages
function initializePages() {
    initializeInferenceModels();
    initializeTargetModels();
    initializeCompositeModels();
    initializeProxySettings();
    initializeWorkflowSettings();
    initializeSystemSettings();
    showWelcome();
}

// Add message display functions
function showError(message) {
    showToast(message, 'error');
}

function showSuccess(message) {
    showToast(message, 'success');
}
