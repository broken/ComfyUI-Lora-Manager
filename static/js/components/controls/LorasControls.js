// LorasControls.js - Specific implementation for the LoRAs page
import { PageControls } from './PageControls.js';
import { getModelApiClient, resetAndReload } from '../../api/modelApiFactory.js';
import { getSessionItem, removeSessionItem } from '../../utils/storageHelpers.js';
import { createAlphabetBar } from '../alphabet/index.js';
import { downloadManager } from '../../managers/DownloadManager.js';

/**
 * LorasControls class - Extends PageControls for LoRA-specific functionality
 */
export class LorasControls extends PageControls {
    constructor() {
        // Initialize with 'loras' page type
        super('loras');
        
        // Register API methods specific to the LoRAs page
        this.registerLorasAPI();
        
        // Check for custom filters (e.g., from recipe navigation)
        this.checkCustomFilters();
        
        // Initialize alphabet bar component
        this.initAlphabetBar();
        
        // Initialize view selector
        this.initViewSelector();
    }
    
    /**
     * Register LoRA-specific API methods
     */
    registerLorasAPI() {
        const lorasAPI = {
            // Core API functions
            loadMoreModels: async (resetPage = false, updateFolders = false) => {
                return await getModelApiClient().loadMoreWithVirtualScroll(resetPage, updateFolders);
            },
            
            resetAndReload: async (updateFolders = false) => {
                return await resetAndReload(updateFolders);
            },
            
            refreshModels: async (fullRebuild = false) => {
                return await getModelApiClient().refreshModels(fullRebuild);
            },
            
            // LoRA-specific API functions
            fetchFromCivitai: async () => {
                return await getModelApiClient().fetchCivitaiMetadata();
            },
            
            showDownloadModal: () => {
                downloadManager.showDownloadModal();
            },
            
            toggleBulkMode: () => {
                if (window.bulkManager) {
                    window.bulkManager.toggleBulkMode();
                } else {
                    console.error('Bulk manager not available');
                }
            },
            
            clearCustomFilter: async () => {
                await this.clearCustomFilter();
            }
        };
        
        // Register the API
        this.registerAPI(lorasAPI);
    }
    
    /**
     * Check for custom filter parameters in session storage (e.g., from recipe page navigation)
     */
    checkCustomFilters() {
        const filterLoraHash = getSessionItem('recipe_to_lora_filterLoraHash');
        const filterLoraHashes = getSessionItem('recipe_to_lora_filterLoraHashes');
        const filterRecipeName = getSessionItem('filterRecipeName');
        const viewLoraDetail = getSessionItem('viewLoraDetail');
        
        if ((filterLoraHash || filterLoraHashes) && filterRecipeName) {
            // Found custom filter parameters, set up the custom filter
            
            // Show the filter indicator
            const indicator = document.getElementById('customFilterIndicator');
            const filterText = indicator?.querySelector('.customFilterText');
            
            if (indicator && filterText) {
                indicator.classList.remove('hidden');
                
                // Set text content with recipe name
                const filterType = filterLoraHash && viewLoraDetail ? "Viewing LoRA from" : "Viewing LoRAs from";
                const displayText = `${filterType}: ${filterRecipeName}`;
                
                filterText.textContent = this._truncateText(displayText, 30);
                filterText.setAttribute('title', displayText);
                
                // Add pulse animation
                const filterElement = indicator.querySelector('.filter-active');
                if (filterElement) {
                    filterElement.classList.add('animate');
                    setTimeout(() => filterElement.classList.remove('animate'), 600);
                }
            }
            
            // If we're viewing a specific LoRA detail, set up to open the modal
            if (filterLoraHash && viewLoraDetail) {
                this.pageState.pendingLoraHash = filterLoraHash;
            }
        }
    }
    
    /**
     * Clear the custom filter and reload the page
     */
    async clearCustomFilter() {
        console.log("Clearing custom filter...");
        // Remove filter parameters from session storage
        removeSessionItem('recipe_to_lora_filterLoraHash');
        removeSessionItem('recipe_to_lora_filterLoraHashes');
        removeSessionItem('filterRecipeName');
        removeSessionItem('viewLoraDetail');
        
        // Hide the filter indicator
        const indicator = document.getElementById('customFilterIndicator');
        if (indicator) {
            indicator.classList.add('hidden');
        }
        
        // Reset state
        if (this.pageState.pendingLoraHash) {
            delete this.pageState.pendingLoraHash;
        }
        
        // Reload the loras
        await resetAndReload();
    }
    
    /**
     * Helper to truncate text with ellipsis
     * @param {string} text - Text to truncate
     * @param {number} maxLength - Maximum length before truncating
     * @returns {string} - Truncated text
     */
    _truncateText(text, maxLength) {
        return text.length > maxLength ? text.substring(0, maxLength - 3) + '...' : text;
    }
    
    /**
     * Initialize the alphabet bar component
     */
    initAlphabetBar() {
        // Create the alphabet bar component
        this.alphabetBar = createAlphabetBar('loras');
        
        // Expose the alphabet bar to the global scope for debugging
        window.alphabetBar = this.alphabetBar;
    }
    
    /**
     * Initialize the view selector component and fetch available views
     */
    async initViewSelector() {
        try {
            const response = await fetch('/api/lm/loras/views/list');
            const data = await response.json();
            
            if (data.success && data.views && data.views.length > 0) {
                const group = document.getElementById('viewSelectorGroup');
                const menu = document.getElementById('viewSelectorMenu');
                
                if (!group || !menu) return;
                
                // Show the view selector
                group.style.display = 'flex';
                
                // Set default view in state if not present
                if (!this.pageState.currentView) {
                    this.pageState.currentView = 'default';
                }
                
                // Add views to menu, formatting grouped paths as a pseudo-tree
                // Calculate folder groupings assuming views are sorted alphabetically
                let lastPathParts = [];
                
                data.views.forEach(viewPath => {
                    const pathParts = viewPath.split('/');
                    const currentName = pathParts[pathParts.length - 1];
                    const currentDepth = pathParts.length - 1;
                    
                    // Add folder headers for path parts that differ from the previous item
                    for (let i = 0; i < currentDepth; i++) {
                        if (i >= lastPathParts.length || pathParts[i] !== lastPathParts[i]) {
                            const header = document.createElement('div');
                            header.className = 'dropdown-header';
                            header.style.paddingLeft = `${0.5 + i * 1.5}rem`;
                            header.innerHTML = `<i class="fas fa-folder"></i> <span>${pathParts[i]}</span>`;
                            menu.appendChild(header);
                        }
                    }
                    
                    lastPathParts = pathParts;

                    const item = document.createElement('div');
                    item.className = 'dropdown-item';
                    item.dataset.view = viewPath;
                    
                    // Add padding proportional to depth for visual hierarchy
                    item.style.paddingLeft = `${1 + currentDepth * 1.5}rem`;
                    
                    if (this.pageState.currentView === viewPath) {
                        item.classList.add('active');
                        document.getElementById('currentViewName').textContent = currentName;
                    }
                    
                    item.innerHTML = `<i class="fas fa-image"></i> <span>${currentName}</span>`;
                    menu.appendChild(item);
                });
                
                // Add click handlers for all items
                menu.addEventListener('click', async (e) => {
                    const item = e.target.closest('.dropdown-item');
                    if (!item) return;
                    
                    const newView = item.dataset.view;
                    
                    // Update active state in UI
                    menu.querySelectorAll('.dropdown-item').forEach(el => el.classList.remove('active'));
                    item.classList.add('active');
                    
                    // Update button text
                    const pathParts = newView.split('/');
                    const viewLabel = newView === 'default' ? 'Screenshot' : pathParts[pathParts.length - 1];
                    document.getElementById('currentViewName').textContent = viewLabel;
                    
                    // Update state
                    this.pageState.currentView = newView;
                    
                    // Reload models to update the DOM with new views
                    await this.api.resetAndReload(false);
                });
            }
        } catch (error) {
            console.error('Error initializing view selector:', error);
        }
    }
}