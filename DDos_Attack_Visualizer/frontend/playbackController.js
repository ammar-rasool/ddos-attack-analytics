/**
 * playbackController.js
 * 
 * Manages the playback lifecycle, including:
 * - Mode switching (Compressed ↔ Real-Time)
 * - Animation loop management
 * - Stopping and resetting playback
 */

window.PlaybackController = class PlaybackController {
    constructor(groupedRows, world, overlay, updateDisplayFn) {
        this.groupedRows = groupedRows;
        this.world = world;
        this.overlay = overlay;
        this.updateDisplayFn = updateDisplayFn;
        
        this.currentMode = null;
        this.animationFrameId = null;
        this.playbackStart = null;
        this.lastWindowIndex = -1;
        this.isPaused = false;
        this.pausedTime = 0;
    }
    
    /**
     * Initialize playback with the given mode
     */
    start(mode) {
        this.stop();
        
        this.currentMode = mode;
        this.lastWindowIndex = -1;
        this.playbackStart = performance.now();
        this.pausedTime = 0;
        this.isPaused = false;
        
        const totalWindows = this.groupedRows.length;
        const durationMs = this.currentMode.getDurationMs(totalWindows);
        
        const animate = (now) => {
            if (this.isPaused) {
                this.animationFrameId = requestAnimationFrame(animate);
                return;
            }
            
            const elapsedMs = now - this.playbackStart;
            const windowIndex = this.currentMode.getWindowIndex(
                elapsedMs,
                totalWindows,
                durationMs
            );
            
            if (windowIndex !== this.lastWindowIndex) {
                const activeWindow = this.groupedRows[windowIndex];
                this.world.arcsData(activeWindow.data);
                
                this.updateDisplayFn({
                    windowIndex,
                    totalWindows,
                    timestamp: activeWindow.timestamp,
                    data: activeWindow.data
                });
                
                this.lastWindowIndex = windowIndex;
            }
            
            this.animationFrameId = requestAnimationFrame(animate);
        };
        
        this.animationFrameId = requestAnimationFrame(animate);
    }
    
    /**
     * Stop the current playback
     */
    stop() {
        if (this.animationFrameId !== null) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        
        this.world.arcsData([]);
        this.lastWindowIndex = -1;
        this.isPaused = false;
    }
    
    /**
     * Pause the playback (can be resumed)
     */
    pause() {
        if (!this.isPaused && this.playbackStart !== null) {
            this.pausedTime = performance.now() - this.playbackStart;
            this.isPaused = true;
        }
    }
    
    /**
     * Resume from pause
     */
    resume() {
        if (this.isPaused) {
            this.playbackStart = performance.now() - this.pausedTime;
            this.isPaused = false;
        }
    }
    
    /**
     * Switch to a new playback mode
     */
    switchMode(newMode) {
        if (this.currentMode && this.currentMode.name === newMode.name) {
            return; // Already in this mode
        }
        
        this.start(newMode);
    }
    
    /**
     * Get the current playback mode
     */
    getMode() {
        return this.currentMode;
    }
};

