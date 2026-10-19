// Playback modes and controllers are loaded via script tags
// using window.PlaybackModes, window.PlaybackController, window.ModeSelector

const API_SOURCES = [
    '/api/combined-ddos-flows',
    '../backend/data/combined_ddos_flows.json'
];

const world = Globe()(document.getElementById('globeViz'))
    .globeImageUrl('//unpkg.com/three-globe/example/img/earth-dark.jpg')
    .backgroundColor('#000000');

world.controls().minDistance = 120;
world.controls().maxDistance = 500;

world
    .arcStartLat(d => d.origin_lat)
    .arcStartLng(d => d.origin_lng)
    .arcEndLat(d => d.target_lat)
    .arcEndLng(d => d.target_lng)
    .arcColor(d => d.attack_layer === 'Layer 7'
        ? ['rgba(0,0,0,0)', 'rgba(0,145,255,0.95)', 'rgba(0,0,0,0)']
        : ['rgba(0,0,0,0)', 'rgba(255,60,60,0.95)', 'rgba(0,0,0,0)'])
    .arcStroke(d => Math.max(0.35, Math.log10(Math.max(10, d.attack_intensity || 0)) * 0.28))
    .arcAltitude(d => Math.min(0.35, 0.05 + Math.log10(Math.max(10, d.attack_intensity || 0)) * 0.012))
    .arcDashLength(0.65)
    .arcDashGap(0.35)
    .arcDashAnimateTime(1800);

const overlay = createOverlay();

function createOverlay() {
    const panel = document.createElement('div');
    panel.style.position = 'absolute';
    panel.style.top = '70px';
    panel.style.left = '16px';
    panel.style.zIndex = '10';
    panel.style.color = 'white';
    panel.style.fontFamily = 'Arial, sans-serif';
    panel.style.background = 'rgba(0,0,0,0.55)';
    panel.style.border = '1px solid rgba(255,255,255,0.18)';
    panel.style.borderRadius = '12px';
    panel.style.padding = '12px 14px';
    panel.style.backdropFilter = 'blur(8px)';
    panel.style.maxWidth = '360px';

    panel.innerHTML = `
        <div style="font-size:16px;font-weight:700;margin-bottom:6px;">DDoS Arc Playback</div>
        <div id="statusText" style="font-size:13px;line-height:1.4;opacity:0.95;">Loading combined flow data…</div>
        <div id="timestampText" style="font-size:13px;line-height:1.4;margin-top:6px;opacity:0.95;"></div>
        <div id="countText" style="font-size:13px;line-height:1.4;margin-top:6px;opacity:0.95;"></div>
    `;

    document.body.appendChild(panel);

    return {
        status: panel.querySelector('#statusText'),
        timestamp: panel.querySelector('#timestampText'),
        count: panel.querySelector('#countText')
    };
}

function setOverlayStatus(message) {
    overlay.status.textContent = message;
}

function setOverlayTimestamp(timestamp, index, total) {
    overlay.timestamp.textContent = `Time window: ${timestamp}`;
    overlay.count.textContent = `Window ${index + 1} of ${total}`;
}

function formatTimestamp(timestamp) {
    const dt = new Date(timestamp);
    if (Number.isNaN(dt.getTime())) {
        return timestamp;
    }
    return dt.toLocaleString();
}

function normalizeRow(row, index) {
    const originLat = Number(row.origin_lat);
    const originLng = Number(row.origin_lng);
    const targetLat = Number(row.target_lat);
    const targetLng = Number(row.target_lng);

    if (![originLat, originLng, targetLat, targetLng].every(Number.isFinite)) {
        return null;
    }

    return {
        ...row,
        __index: index,
        attack_layer: row.attack_layer || row.layer || 'Layer 3',
        attack_intensity: Number(row.attack_intensity ?? row.attacks ?? 0),
        origin_lat: originLat,
        origin_lng: originLng,
        target_lat: targetLat,
        target_lng: targetLng,
        timestamp: row.timestamp || ''
    };
}

function groupByTimestamp(rows) {
    const groups = new Map();

    rows.forEach((row) => {
        const key = row.timestamp || 'Unknown time';
        if (!groups.has(key)) {
            groups.set(key, []);
        }
        groups.get(key).push(row);
    });

    return Array.from(groups.entries())
        .map(([timestamp, data]) => ({ timestamp, data }))
        .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

async function fetchAttackData() {
    let lastError = null;

    for (const source of API_SOURCES) {
        try {
            const response = await fetch(source, { cache: 'no-store' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            lastError = error;
        }
    }

    throw lastError || new Error('Unable to load attack data.');
}

async function loadCountryBoundaries() {
    const response = await fetch(
        'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson'
    );
    const countries = await response.json();

    world
        .polygonsData(countries.features)
        .polygonCapColor(() => 'rgba(0,0,0,0)')
        .polygonSideColor(() => 'rgba(0,0,0,0)')
        .polygonStrokeColor(() => '#ffffff');

    const countryLabels = countries.features
        .filter(d => d.properties.NAME !== 'Antarctica')
        .map(d => {
            let targetFeature = d;

            if (d.geometry.type === 'MultiPolygon') {
                let maxArea = -1;
                let largestPolygon = null;

                d.geometry.coordinates.forEach(polygonCoords => {
                    const tempFeature = {
                        type: 'Feature',
                        geometry: { type: 'Polygon', coordinates: polygonCoords }
                    };
                    const area = d3.geoArea(tempFeature);
                    if (area > maxArea) {
                        maxArea = area;
                        largestPolygon = tempFeature;
                    }
                });

                if (largestPolygon) {
                    targetFeature = largestPolygon;
                }
            }

            const [lng, lat] = d3.geoCentroid(targetFeature);

            return {
                name: d.properties.NAME.toUpperCase(),
                lat,
                lng
            };
        });

    // // Manually add text labels for territories missing from the 110m GeoJSON map
    // countryLabels.push(
    //     { name: 'PUERTO RICO', lat: 18.2208, lng: -66.5901 },
    //     { name: 'CURAÇAO', lat: 12.1696, lng: -68.9900 },
    //     { name: 'JERSEY', lat: 49.2144, lng: -2.1312 },
    //     { name: 'REUNION', lat: -21.1151, lng: 55.5364 },
    //     { name: 'HONG KONG', lat: 22.3193, lng: 114.1694 },
    //     { name: 'FRENCH POLYNESIA', lat: -17.6797, lng: -149.4068 }
    // );

    // world
    //     .htmlElementsData(countryLabels)

    world
        .htmlElementsData(countryLabels)
        .htmlLat(d => d.lat)
        .htmlLng(d => d.lng)
        .htmlElement(d => {
            const el = document.createElement('div');
            el.className = 'country-label';
            el.textContent = d.name;
            el.style.color = 'white';
            el.style.fontSize = '14px';
            el.style.fontWeight = 'bold';
            el.style.fontFamily = 'Times New Roman, serif';
            el.style.pointerEvents = 'none';
            el.style.userSelect = 'none';
            el.style.whiteSpace = 'nowrap';
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.5s ease';
            return el;
        });

    function updateLabelOpacity() {
        const distance = world.camera().position.length();
        const opacity = Math.max(0, Math.min(1, (250 - distance) / 100));
        document.querySelectorAll('.country-label').forEach(el => {
            el.style.opacity = opacity;
        });
    }

    world.controls().addEventListener('change', updateLabelOpacity);
    updateLabelOpacity();
}

async function main() {
    try {
        // Verify all required global classes are loaded
        if (!window.PlaybackModes || !window.PlaybackController || !window.ModeSelector) {
            throw new Error('Playback modules not loaded. Check browser console.');
        }
        
        console.log('✓ All playback modules ready');
        
        await loadCountryBoundaries();

        const rawData = await fetchAttackData();
        const rows = Array.isArray(rawData)
            ? rawData.map(normalizeRow).filter(Boolean)
            : [];

        if (!rows.length) {
            setOverlayStatus('No attack rows were found in combined_ddos_flows.json.');
            world.arcsData([]);
            return;
        }

        const groupedRows = groupByTimestamp(rows);

        // Create mode selector
        console.log('Creating mode selector...');
        const modeSelector = new window.ModeSelector((selectedMode) => {
            console.log('Mode changed to:', selectedMode.name);
            playbackController.switchMode(selectedMode);
        });
        
        const modes = [window.PlaybackModes.COMPRESSED, window.PlaybackModes.REALTIME];
        console.log('Modes array:', modes);
        modeSelector.create(modes);
        console.log('✓ Mode selector created successfully');

        // Create display update function
        const updateDisplay = (displayInfo) => {
            const { windowIndex, totalWindows, timestamp, data } = displayInfo;
            
            const modeDisplay = modeSelector.getActiveMode().displayName;
            setOverlayStatus(`[${modeDisplay}] Loaded ${rows.length.toLocaleString()} records`);
            setOverlayTimestamp(formatTimestamp(timestamp), windowIndex, totalWindows);

            const l7Count = data.filter(d => d.attack_layer === 'Layer 7').length;
            const l3Count = data.length - l7Count;
            overlay.count.textContent = `Window ${windowIndex + 1} / ${totalWindows} | Layer 7: ${l7Count.toLocaleString()} | Layer 3: ${l3Count.toLocaleString()}`;
        };

        // Create playback controller
        const playbackController = new window.PlaybackController(
            groupedRows,
            world,
            overlay,
            updateDisplay
        );

        // Start with compressed mode
        modeSelector.selectMode(window.PlaybackModes.COMPRESSED);
        playbackController.start(window.PlaybackModes.COMPRESSED);
        console.log('✓ Playback started in COMPRESSED mode');

    } catch (error) {
        console.error('ERROR in main():', error);
        setOverlayStatus('Error: ' + (error?.message || error));
        overlay.timestamp.textContent = String(error?.stack || error);
        overlay.count.textContent = '';
        world.arcsData([]);
    }
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
} else {
    main();
}