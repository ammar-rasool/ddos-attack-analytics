/**
 * modeSelector.js
 * 
 * Creates and manages the playback mode selector UI.
 * Provides a segmented control with visual feedback for the active mode.
 */

window.ModeSelector = class ModeSelector {
    constructor(onModeChange) {
        this.onModeChange = onModeChange;
        this.activeMode = null;
        this.container = null;
        this.buttons = new Map();
    }
    
    /**
     * Create the mode selector UI element
     */
    create(modes) {
        // Main container
        this.container = document.createElement('div');
        this.container.style.position = 'absolute';
        this.container.style.top = '16px';
        this.container.style.left = '50%';
        this.container.style.transform = 'translateX(-50%)';
        this.container.style.zIndex = '11';
        this.container.style.display = 'flex';
        this.container.style.gap = '4px';
        this.container.style.padding = '6px';
        this.container.style.background = 'rgba(0,0,0,0.55)';
        this.container.style.border = '1px solid rgba(255,255,255,0.18)';
        this.container.style.borderRadius = '12px';
        this.container.style.backdropFilter = 'blur(8px)';
        this.container.style.fontFamily = 'Arial, sans-serif';
        
        // Create buttons for each mode
        modes.forEach((mode) => {
            const button = document.createElement('button');
            button.className = 'mode-selector-button';
            button.textContent = mode.displayName;
            button.dataset.mode = mode.name;
            
            // Base button styles
            button.style.cursor = 'pointer';
            button.style.border = 'none';
            button.style.padding = '8px 16px';
            button.style.borderRadius = '8px';
            button.style.fontSize = '13px';
            button.style.fontWeight = '500';
            button.style.transition = 'all 0.28s cubic-bezier(0.4, 0, 0.2, 1)';
            button.style.outline = 'none';
            button.style.userSelect = 'none';
            button.style.whiteSpace = 'nowrap';
            
            button.addEventListener('click', () => {
                this.selectMode(mode);
                this.onModeChange(mode);
            });
            
            this.buttons.set(mode.name, button);
            this.container.appendChild(button);
        });
        
        document.body.appendChild(this.container);
        console.log('✓ ModeSelector UI created and appended to body');
    }
    
    /**
     * Visually select a mode button
     */
    selectMode(mode) {
        // Update all buttons
        this.buttons.forEach((button, modeName) => {
            const isActive = modeName === mode.name;
            
            if (isActive) {
                // Active button: bright, highlighted, slightly scaled up
                button.style.background = 'rgba(0, 145, 255, 0.9)';
                button.style.color = '#ffffff';
                button.style.boxShadow = '0 4px 12px rgba(0, 145, 255, 0.4), inset 0 1px 0 rgba(255,255,255,0.2)';
                button.style.transform = 'scale(1.05)';
                button.style.opacity = '1';
            } else {
                // Inactive button: dim, slightly pressed appearance
                button.style.background = 'rgba(100, 100, 100, 0.3)';
                button.style.color = 'rgba(255, 255, 255, 0.6)';
                button.style.boxShadow = 'inset 0 2px 4px rgba(0,0,0,0.3)';
                button.style.transform = 'scale(0.98)';
                button.style.opacity = '0.7';
            }
        });
        
        this.activeMode = mode;
    }
    
    /**
     * Get the currently selected mode
     */
    getActiveMode() {
        return this.activeMode;
    }
    
    /**
     * Remove the UI element
     */
    destroy() {
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        this.buttons.clear();
    }
};

