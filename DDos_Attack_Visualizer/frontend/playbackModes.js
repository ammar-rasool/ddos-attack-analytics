/**
 * playbackModes.js
 * 
 * Provides two distinct playback timing strategies for the DDoS visualization:
 * 1. COMPRESSED: 24-hour dataset compressed into 3 minutes
 * 2. REALTIME: 24-hour dataset played back in real-time (24 hours)
 */

window.PlaybackModes = {
    /**
     * COMPRESSED MODE
     * Compresses the entire 24-hour dataset into exactly 3 minutes (180 seconds).
     * All records are shown in chronological order but at accelerated speed.
     */
    COMPRESSED: {
        name: 'COMPRESSED',
        displayName: '3-Minute Playback',
        
        getDurationMs(totalWindows) {
            // Always 3 minutes (180,000 milliseconds) regardless of data
            return 180_000;
        },
        
        getWindowIndex(elapsedMs, totalWindows, durationMs) {
            // Cycle through all windows in the compressed timeframe
            const cycledElapsed = elapsedMs % durationMs;
            const windowDurationMs = durationMs / totalWindows;
            return Math.min(totalWindows - 1, Math.floor(cycledElapsed / windowDurationMs));
        },
        
        getProgressPercent(elapsedMs, totalWindows, durationMs) {
            const cycledElapsed = elapsedMs % durationMs;
            return (cycledElapsed / durationMs) * 100;
        }
    },
    
    /**
     * REAL-TIME MODE
     * Plays back the 24-hour dataset at real-time speed.
     * Each 15-minute interval in the data represents 15 real minutes of playback.
     * The entire visualization takes 24 real hours to complete.
     */
    REALTIME: {
        name: 'REALTIME',
        displayName: '24-Hour Real-Time',
        
        getDurationMs(totalWindows) {
            // Each window represents 15 minutes of real time
            // With ~96 windows in 24 hours, total duration is 24 * 60 * 60 * 1000
            const FIFTEEN_MINUTES_MS = 15 * 60 * 1000;
            return totalWindows * FIFTEEN_MINUTES_MS;
        },
        
        getWindowIndex(elapsedMs, totalWindows, durationMs) {
            // Do NOT cycle - clamp at the last window when playback completes
            const FIFTEEN_MINUTES_MS = 15 * 60 * 1000;
            const windowIndex = Math.floor(elapsedMs / FIFTEEN_MINUTES_MS);
            return Math.min(totalWindows - 1, windowIndex);
        },
        
        getProgressPercent(elapsedMs, totalWindows, durationMs) {
            // Progress does not wrap around - it plays once
            return Math.min(100, (elapsedMs / durationMs) * 100);
        }
    }
};

