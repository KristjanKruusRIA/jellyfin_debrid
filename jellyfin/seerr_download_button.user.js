// ==UserScript==
// @name         Seerr JD Search Button
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Add a Search button on Seerr movie/TV pages to deep-link to Jellyfin Debrid
// @match        http://192.168.1.169:5055/*
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    // Inject the entire script into the page context to avoid sandbox restrictions
    const script = document.createElement('script');
    script.textContent = `
    (function() {
        let lastProcessedUrl = null;
        let injectionAttemptInterval = null;

        // Button style matching Seerr's design
        const style = document.createElement('style');
        style.textContent = \`
            .jd-search-btn {
                background: #4ec9b0 !important;
                color: #1e1e1e !important;
                border: none !important;
                border-radius: 9999px !important;
                padding: 8px 16px !important;
                font-weight: 600 !important;
                font-size: 14px !important;
                cursor: pointer !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 6px !important;
                transition: opacity 0.2s !important;
                box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
            }
            .jd-search-btn:hover {
                opacity: 0.9 !important;
            }
        \`;
        document.head.appendChild(style);

        function getMediaInfoFromUrl() {
            const match = window.location.pathname.match(/^\\/(movie|tv)\\/(\\d+)/);
            if (match) {
                return {
                    mediaType: match[1],
                    tmdbId: match[2]
                };
            }
            return null;
        }

        function handleSearchClick(mediaType, tmdbId) {
            const searchUrl = \`http://192.168.1.169:7654/search?tmdb_id=\${tmdbId}&media_type=\${mediaType}\`;
            window.open(searchUrl, '_blank');
        }

        function injectButton() {
            const mediaInfo = getMediaInfoFromUrl();
            if (!mediaInfo) return;

            // Check if we already have the button on this page
            if (document.querySelector('.jd-search-btn')) {
                // Return true to indicate successful/existing injection
                return true;
            }

            // Find the action buttons container
            const buttons = Array.from(document.querySelectorAll('button'));

            // Look for common action buttons in Seerr
            const actionBtn = buttons.find(b => {
                const text = b.textContent.toLowerCase();
                return (
                    text.includes('request') ||
                    text.includes('available') ||
                    text.includes('play trailer') ||
                    text.includes('report issue') ||
                    text.includes('pending') ||
                    text.includes('approved') ||
                    text.includes('declined') ||
                    text.includes('processing')
                );
            });

            if (!actionBtn) return false;

            const buttonContainer = actionBtn.parentElement;
            if (!buttonContainer) return false;

            const searchBtn = document.createElement('button');
            searchBtn.className = 'jd-search-btn';
            searchBtn.setAttribute('data-jd-processed', 'true');
            searchBtn.innerHTML = '<span>🔍</span><span>Search</span>';

            searchBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                handleSearchClick(mediaInfo.mediaType, mediaInfo.tmdbId);
            });

            buttonContainer.appendChild(searchBtn);
            return true;
        }

        function checkAndInject() {
            const currentUrl = window.location.pathname;
            const mediaInfo = getMediaInfoFromUrl();

            if (!mediaInfo) {
                lastProcessedUrl = null;
                if (injectionAttemptInterval) {
                    clearInterval(injectionAttemptInterval);
                    injectionAttemptInterval = null;
                }
                return;
            }

            // If we navigated to a new media page, start trying to inject
            if (currentUrl !== lastProcessedUrl) {
                lastProcessedUrl = currentUrl;

                if (injectionAttemptInterval) {
                    clearInterval(injectionAttemptInterval);
                }

                // Try to inject immediately
                if (!injectButton()) {
                    // If it failed (DOM not ready), try periodically
                    injectionAttemptInterval = setInterval(() => {
                        if (injectButton()) {
                            clearInterval(injectionAttemptInterval);
                            injectionAttemptInterval = null;
                        }
                    }, 500);
                }
            } else {
                // Same URL, but check if button was removed by React re-render
                if (!document.querySelector('.jd-search-btn')) {
                    injectButton();
                }
            }
        }

        // Observe DOM changes for single-page app navigation/rendering
        const observer = new MutationObserver(() => {
            checkAndInject();
        });

        function init() {
            if (document.body) {
                checkAndInject();
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            } else {
                setTimeout(init, 100);
            }
        }

        init();
    })();
    `;
    document.body.appendChild(script);
})();
