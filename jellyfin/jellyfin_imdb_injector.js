(function() {
    'use strict';

    const LOG_PREFIX = '[IMDB Injector]';
    const JELLYSEERR_BASE_URL = 'http://192.168.1.169:5055';
    const JELLYSEERR_API_KEY = 'MTc2ODM4MjQxODQ1NjE3NmM2ZTUzLTFmNzgtNDAwMS04ZDkwLWU5YzdiMTY5NWQzOQ==';
    const processed = new Set();
    const CHECK_INTERVAL = 10000;

    function log(...args) {
        console.debug(LOG_PREFIX, ...args);
    }

    // CSS for rating badges
    const style = document.createElement('style');
    style.textContent = `
        .rating-badges-container {
            position: absolute !important;
            bottom: 8px !important;
            left: 8px !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 4px !important;
            z-index: 99999 !important;
            pointer-events: none !important;
        }
        .rating-badge {
            background: rgba(0, 0, 0, 0.85) !important;
            padding: 3px 6px !important;
            border-radius: 3px !important;
            font-weight: bold !important;
            font-size: 11px !important;
            display: flex !important;
            align-items: center !important;
            gap: 3px !important;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.5) !important;
            white-space: nowrap !important;
        }
        .rating-badge.tmdb {
            color: #01d277 !important;
        }
        .rating-badge.imdb {
            color: #f5c518 !important;
        }
        .rating-badge.rt {
            color: #fa320a !important;
        }
    `;
    document.head.appendChild(style);

    // Fetch ratings from Jellyseerr API
    async function getRatings(tmdbId, mediaType) {
        try {
            const ratings = {};
            
            // Fetch main data for TMDB score
            const mainUrl = `${JELLYSEERR_BASE_URL}/api/v1/${mediaType}/${tmdbId}`;
            const mainResponse = await fetch(mainUrl, {
                method: 'GET',
                headers: {
                    'X-Api-Key': JELLYSEERR_API_KEY,
                    'Accept': 'application/json'
                },
                mode: 'cors',
                credentials: 'omit'
            });
            
            if (mainResponse.ok) {
                const mainData = await mainResponse.json();
                if (mainData.voteAverage) {
                    ratings.tmdb = mainData.voteAverage;
                }
            }
            
            // Fetch additional ratings based on media type
            if (mediaType === 'movie') {
                // For movies: use ratingscombined endpoint for IMDB and RT
                const ratingsUrl = `${JELLYSEERR_BASE_URL}/api/v1/${mediaType}/${tmdbId}/ratingscombined`;
                const ratingsResponse = await fetch(ratingsUrl, {
                    method: 'GET',
                    headers: {
                        'X-Api-Key': JELLYSEERR_API_KEY,
                        'Accept': 'application/json'
                    },
                    mode: 'cors',
                    credentials: 'omit'
                });
                
                if (ratingsResponse.ok) {
                    const ratingsData = await ratingsResponse.json();
                    
                    // Extract IMDB score
                    if (ratingsData.imdb && ratingsData.imdb.criticsScore) {
                        ratings.imdb = ratingsData.imdb.criticsScore;
                    }
                    
                    // Extract Rotten Tomatoes score
                    if (ratingsData.rt && ratingsData.rt.criticsScore) {
                        ratings.rt = ratingsData.rt.criticsScore;
                    }
                }
            } else if (mediaType === 'tv') {
                // For TV shows: use ratings endpoint for RT only
                const ratingsUrl = `${JELLYSEERR_BASE_URL}/api/v1/${mediaType}/${tmdbId}/ratings`;
                const ratingsResponse = await fetch(ratingsUrl, {
                    method: 'GET',
                    headers: {
                        'X-Api-Key': JELLYSEERR_API_KEY,
                        'Accept': 'application/json'
                    },
                    mode: 'cors',
                    credentials: 'omit'
                });
                
                if (ratingsResponse.ok) {
                    const ratingsData = await ratingsResponse.json();
                    
                    // Extract Rotten Tomatoes score
                    if (ratingsData.criticsScore) {
                        ratings.rt = ratingsData.criticsScore;
                    }
                }
            }
            
            return Object.keys(ratings).length > 0 ? ratings : null;
        } catch (error) {
            console.error(LOG_PREFIX, 'CORS Error - Jellyseerr needs to allow requests from', window.location.origin);
            return null;
        }
    }

    // Add rating badges to card
    function addRatingBadges(card, ratings) {
        const cardScalable = card.querySelector('.cardScalable');
        if (!cardScalable) {
            return;
        }
        
        // Remove existing container if present
        const existingContainer = cardScalable.querySelector('.rating-badges-container');
        if (existingContainer) {
            existingContainer.remove();
        }

        // Create container for all badges
        const container = document.createElement('div');
        container.className = 'rating-badges-container';
        
        // Add TMDB badge if available
        if (ratings.tmdb) {
            const tmdbBadge = document.createElement('div');
            tmdbBadge.className = 'rating-badge tmdb';
            tmdbBadge.innerHTML = `TMDB ${ratings.tmdb.toFixed(1)}`;
            tmdbBadge.title = `TMDB Rating: ${ratings.tmdb.toFixed(1)}/10`;
            container.appendChild(tmdbBadge);
        }
        
        // Add IMDB badge if available
        if (ratings.imdb) {
            const imdbBadge = document.createElement('div');
            imdbBadge.className = 'rating-badge imdb';
            imdbBadge.innerHTML = `IMDB ${ratings.imdb.toFixed(1)}`;
            imdbBadge.title = `IMDB Rating: ${ratings.imdb.toFixed(1)}/10`;
            container.appendChild(imdbBadge);
        }
        
        // Add Rotten Tomatoes badge if available
        if (ratings.rt) {
            const rtBadge = document.createElement('div');
            rtBadge.className = 'rating-badge rt';
            rtBadge.innerHTML = `RT ${ratings.rt}%`;
            rtBadge.title = `Rotten Tomatoes: ${ratings.rt}%`;
            container.appendChild(rtBadge);
        }
        
        // Only add container if we have at least one rating
        if (container.children.length > 0) {
            cardScalable.style.position = 'relative';
            cardScalable.style.overflow = 'visible';
            cardScalable.appendChild(container);
        }
    }

    // Process a single discover card
    async function processCard(card) {
        const cardIndex = card.getAttribute('data-index');
        
        const requestButton = card.querySelector('button.discover-requestbutton[data-id]');
        if (!requestButton) {
            return;
        }

        const tmdbId = requestButton.getAttribute('data-id');
        const mediaType = requestButton.getAttribute('data-media-type');
        
        if (!tmdbId || !mediaType) {
            return;
        }

        // Find parent section to make key truly unique across different sections
        const section = card.closest('.verticalSection');
        const sectionClass = section ? section.className : 'unknown';
        
        // Create unique key combining section, mediaType, and index to avoid collisions
        const uniqueKey = `${sectionClass}-${mediaType}-${cardIndex}`;
        
        if (processed.has(uniqueKey)) {
            return;
        }

        processed.add(uniqueKey);
        card.setAttribute('data-imdb-processed', 'true');

        const ratings = await getRatings(tmdbId, mediaType);
        if (ratings) {
            addRatingBadges(card, ratings);
        }
    }

    // Find and process all Jellyseerr discover cards
    function processAllCards() {
        const cards = document.querySelectorAll('.discover-card');
        
        cards.forEach(card => {
            processCard(card);
        });
    }

    // Observe DOM changes
    const observer = new MutationObserver(() => {
        processAllCards();
    });

    // Initialize
    processAllCards();
    setInterval(processAllCards, CHECK_INTERVAL);
    
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
})();
