/**
 * Search functionality for speaker database
 */

// Set example query
function setQuery(query) {
    document.getElementById('searchInput').value = query;
    document.getElementById('searchInput').focus();
}

// Perform search
async function performSearch(event) {
    if (event) {
        event.preventDefault();
    }

    const query = document.getElementById('searchInput').value.trim();
    const limit = parseInt(document.getElementById('limitSelect').value);
    const explain = document.getElementById('explainCheck').checked;

    if (!query) {
        showError('Please enter a search query');
        return;
    }

    // Show loading state
    showLoading();
    hideError();
    hideEmptyState();

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query, limit, explain })
        });

        const data = await response.json();

        if (data.success) {
            displayResults(data.results, data.query);
        } else {
            showError(data.error || 'Search failed');
        }
    } catch (error) {
        showError('Network error: ' + error.message);
    } finally {
        hideLoading();
    }
}

// Display search results
function displayResults(results, query) {
    const container = document.getElementById('resultsContainer');
    const header = document.getElementById('resultsHeader');
    const countElement = document.getElementById('resultCount');
    const queryDisplay = document.getElementById('queryDisplay');

    // Clear previous results
    container.innerHTML = '';

    if (results.length === 0) {
        showNoResults(query);
        return;
    }

    // Update header
    countElement.textContent = results.length;
    queryDisplay.textContent = `for "${query}"`;
    header.classList.remove('hidden');

    // Create result cards
    results.forEach(speaker => {
        const card = createSpeakerCard(speaker);
        container.appendChild(card);
    });
}

// Create speaker result card
function createSpeakerCard(speaker) {
    const card = document.createElement('div');
    card.className = 'result-card bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition cursor-pointer';
    card.onclick = () => window.location.href = `/speaker/${speaker.speaker_id}`;

    // Score badge
    const scoreColor = getScoreColor(speaker.score);
    const scoreHTML = `
        <span class="score-badge score-${scoreColor} px-3 py-1 rounded-full text-sm font-bold">
            ${speaker.score.toFixed(2)}
        </span>
    `;

    // Name and title
    const nameHTML = `
        <div class="flex items-start justify-between mb-2">
            <div class="flex-grow">
                <h3 class="text-xl font-bold text-gray-800 hover:text-blue-600">
                    ${escapeHtml(speaker.name)}
                </h3>
                ${speaker.title ? `<p class="text-gray-600 mt-1">${escapeHtml(speaker.title)}</p>` : ''}
                ${speaker.affiliation ? `<p class="text-blue-600 font-medium mt-1">${escapeHtml(speaker.affiliation)}</p>` : ''}
            </div>
            <div class="ml-4">
                ${scoreHTML}
            </div>
        </div>
    `;

    // Tags
    let tagsHTML = '';
    if (speaker.tags && speaker.tags.length > 0) {
        const topTags = speaker.tags.slice(0, 5);
        tagsHTML = `
            <div class="flex flex-wrap gap-2 mb-3">
                ${topTags.map(tag => {
                    const tagColor = getTagColor(tag[1]);
                    const tagText = tag[0];
                    const tagConf = tag[1] ? (tag[1] * 100).toFixed(0) + '%' : '';
                    return `<span class="tag-pill tag-${tagColor} px-2 py-1 rounded-full text-xs font-medium">
                        ${escapeHtml(tagText)} ${tagConf ? `<span class="opacity-75">(${tagConf})</span>` : ''}
                    </span>`;
                }).join('')}
            </div>
        `;
    }

    // Bio excerpt
    let bioHTML = '';
    if (speaker.bio) {
        const excerpt = speaker.bio.length > 200
            ? speaker.bio.substring(0, 200) + '...'
            : speaker.bio;
        bioHTML = `<p class="text-gray-700 text-sm mb-3">${escapeHtml(excerpt)}</p>`;
    }

    // Event count and explanations
    let footerHTML = `
        <div class="flex items-center text-sm text-gray-600">
            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
            </svg>
            <span>${speaker.event_count} event${speaker.event_count !== 1 ? 's' : ''}</span>
    `;

    if (speaker.explanation && speaker.explanation.length > 0) {
        footerHTML += `
            <span class="mx-2">•</span>
            <span class="text-green-600">${speaker.explanation.join(', ')}</span>
        `;
    }

    footerHTML += '</div>';

    // Assemble card
    card.innerHTML = nameHTML + tagsHTML + bioHTML + footerHTML;

    return card;
}

// Get score color
function getScoreColor(score) {
    if (score >= 0.6) return 'green';
    if (score >= 0.4) return 'yellow';
    return 'gray';
}

// Get tag color based on confidence
function getTagColor(confidence) {
    if (!confidence) return 'gray';
    if (confidence > 0.8) return 'green';
    if (confidence > 0.6) return 'blue';
    return 'gray';
}

// Show loading spinner
function showLoading() {
    document.getElementById('searchSpinner').classList.remove('hidden');
    document.getElementById('resultsContainer').innerHTML = '';
    document.getElementById('resultsHeader').classList.add('hidden');
}

// Hide loading spinner
function hideLoading() {
    document.getElementById('searchSpinner').classList.add('hidden');
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    const errorText = document.getElementById('errorText');
    errorText.textContent = message;
    errorDiv.classList.remove('hidden');
}

// Hide error message
function hideError() {
    document.getElementById('errorMessage').classList.add('hidden');
}

// Show empty state
function showEmptyState() {
    document.getElementById('emptyState').classList.remove('hidden');
}

// Hide empty state
function hideEmptyState() {
    document.getElementById('emptyState').classList.add('hidden');
}

// Show no results message
function showNoResults(query) {
    const container = document.getElementById('resultsContainer');
    container.innerHTML = `
        <div class="bg-yellow-50 border border-yellow-200 text-yellow-800 px-6 py-8 rounded-lg text-center">
            <svg class="w-16 h-16 mx-auto mb-4 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
            </svg>
            <p class="text-xl font-semibold mb-2">No speakers found</p>
            <p class="text-sm">Try a different query or broader search terms</p>
        </div>
    `;
    document.getElementById('resultsHeader').classList.add('hidden');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + K to focus search
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        document.getElementById('searchInput').focus();
    }
});

// Auto-focus search input on page load
window.addEventListener('load', function() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.focus();
    }
});
