/**
 * Shared utility helpers for IPX Displays (index.html & rosters.html)
 */

function toSentenceCase(str) {
  if (!str) return '';
  return String(str).replace(/([^\W_]+[^\s-]*) */g, (txt) => {
    return txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase();
  }).trim();
}

function cleanCourtName(rawName) {
  if (!rawName) return '';
  return String(rawName)
    .replace(/\s*\(\s*Livestreaming\s*\)/gi, '')
    .replace(/\s*\(\s*Streaming\s*\)/gi, '')
    .replace(/^Court\s*/i, '')
    .trim();
}

function cleanTitle(rawTitle) {
  if (!rawTitle) return '';
  let firstSegment = String(rawTitle).split('|')[0].trim();

  // Shorten Pickleball for Parkinson's to P4P
  firstSegment = firstSegment.replace(/Pickleball\s+for\s+Parkinson'?s/gi, 'P4P');

  firstSegment = firstSegment
    .replace(/\bSessions?\b/gi, '')
    .replace(/\bOpen\s*Play\b/gi, '')
    .replace(/\bPrime\s*Time\b/gi, '');

  firstSegment = firstSegment.replace(/[-–—/,\s]+$/, '').trim();
  firstSegment = firstSegment.replace(/(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)/g, '$1 \u2013 $2');

  let formatted = toSentenceCase(firstSegment);
  // Preserve uppercase P4P styling
  return formatted.replace(/\bP4p\b/gi, 'P4P');
}

function formatTime(isoString, isEndTime = false) {
  if (!isoString) return '';
  const d = new Date(isoString);

  // Late-night CourtReserve truncations (23:59 -> 1:00 AM)
  if (isEndTime && d.getHours() === 23 && d.getMinutes() === 59) {
    return '1:00 AM';
  }

  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true });
}

function formatTimeWindow(startIso, endIso) {
  if (!startIso || !endIso) return '';
  const t1 = formatTime(startIso, false);
  const t2 = formatTime(endIso, true);
  const parts1 = t1.split(' ');
  const parts2 = t2.split(' ');
  if (parts1.length === 2 && parts2.length === 2 && parts1[1] === parts2[1]) {
    return `${parts1[0]} \u2013 ${t2}`;
  }
  return `${t1} \u2013 ${t2}`;
}
