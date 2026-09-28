// --- IPX Common Engine ---

const themeDisplayNames = {
  'theme-tiffany': 'Tiffany',
  'theme-usopen': 'US Open',
  'theme-apple': 'Apple',
  'theme-rolex': 'Rolex',
  'theme-porsche': 'Porsche',
  'theme-rolandgarros': 'Roland-Garros',
  'theme-ausopen': 'Australian Open',
  'theme-vice': 'Miami Vice',
  'theme-gulfracing': 'Gulf Racing',
  'theme-masters': 'Masters',
  'theme-wimbledon': 'Wimbledon',
  'theme-monaco': 'Monaco GP',
  'theme-cyberpunk': 'Tokyo Cyberpunk',
  'theme-ferrari': 'Ferrari Corsa',
  'theme-glacier': 'Nordic Glacier',
  'theme-desertclay': 'Desert Clay',
  'theme-astonmartin': 'Aston Martin AMR',
  'theme-solarflare': 'Solar Flare',
  'theme-stealth': 'Stealth Titanium',
  'theme-lakers': 'Showtime',
  'theme-yankees': 'NY Yankees',
  'theme-mets': 'NY Mets',
  'theme-knicks': 'NY Knicks',
  'theme-nets': 'Brooklyn Nets',
  'theme-liberty': 'NY Liberty',
  'theme-giants': 'NY Giants',
  'theme-jets': 'NY Jets',
  'theme-rangers': 'NY Rangers',
  'theme-islanders': 'NY Islanders',
  'theme-nycfc': 'NYCFC'
};

const urlParams = new URLSearchParams(window.location.search);
const hasExplicitAhead = urlParams.has('ahead');
const isNamed60 = window.location.pathname.includes('60');
const defaultAhead = isNamed60 ? '60' : '15';
const lookaheadMinutes = parseInt(urlParams.get('ahead') || defaultAhead, 10);
const isPreview = hasExplicitAhead && lookaheadMinutes !== 15;

const cycleParam = urlParams.get('cycle');
const isCycling = cycleParam !== null && cycleParam !== 'false';
const cycleSeconds = (isCycling && !isNaN(parseInt(cycleParam, 10)))
  ? Math.max(1, parseInt(cycleParam, 10))
  : 10;
let cycleIndex = 0;

let nextTransitionTargetEpoch = null;

function updateClock() {
  const now = new Date();
  const clockEl = document.getElementById('live-clock');
  if (clockEl) {
    clockEl.textContent = now.toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  }
  updateCountdown();
}
setInterval(updateClock, 1000);
updateClock();

function updateCountdown() {
  const countdownBox = document.getElementById('countdown-box');
  const countdownVal = document.getElementById('transition-countdown');
  if (!countdownBox || !countdownVal) return;

  if (!nextTransitionTargetEpoch) {
    countdownBox.classList.remove('is-active');
    return;
  }

  const diffMs = nextTransitionTargetEpoch - Date.now();
  if (diffMs > 0 && diffMs <= 15 * 60 * 1000) {
    const totalSecs = Math.floor(diffMs / 1000);
    const m = Math.floor(totalSecs / 60);
    const s = totalSecs % 60;
    countdownVal.textContent = String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    countdownBox.classList.add('is-active');
  } else {
    countdownBox.classList.remove('is-active');
  }
}

function applyDynamicTheme(targetTime) {
  const allThemes = Object.keys(themeDisplayNames);
  let themeToApply = 'theme-apple';

  if (isCycling) {
    themeToApply = allThemes[cycleIndex % allThemes.length];
  } else {
    const urlTheme = (urlParams.get('theme') || '').toLowerCase().trim();
    if (urlTheme && allThemes.includes('theme-' + urlTheme)) {
      themeToApply = 'theme-' + urlTheme;
    } else {
      const totalMinutes = targetTime.getHours() * 60 + targetTime.getMinutes();
      if (totalMinutes >= 420 && totalMinutes < 660) {
        themeToApply = 'theme-tiffany';
      } else if (totalMinutes >= 660 && totalMinutes < 1035) {
        themeToApply = 'theme-usopen';
      } else if (totalMinutes >= 1035 && totalMinutes < 1155) {
        themeToApply = 'theme-apple';
      } else if (totalMinutes >= 1155 && totalMinutes < 1275) {
        themeToApply = 'theme-rolex';
      } else {
        themeToApply = 'theme-porsche';
      }
    }
  }

  document.body.classList.remove(...allThemes);
  document.body.classList.add(themeToApply);

  const displayName = themeDisplayNames[themeToApply] || 'Default';
  const themePill = document.getElementById('theme-pill');
  if (themePill) {
    themePill.textContent = isCycling
      ? 'Theme: ' + displayName + ' (' + ((cycleIndex % allThemes.length) + 1) + '/' + allThemes.length + ')'
      : 'Theme: ' + displayName;
  }
}

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

function extractSortedCourts(courtsRaw) {
  if (!courtsRaw) return [];
  const list = Array.isArray(courtsRaw) ? courtsRaw : [courtsRaw];
  return list
    .map(c => cleanCourtName(c && c.CourtName ? c.CourtName : c))
    .filter(Boolean)
    .sort((a, b) => (parseInt(a, 10) || a) - (parseInt(b, 10) || b));
}

function formatCourtsLabel(courts, mode) {
  mode = mode || 'index';
  const arr = Array.isArray(courts) ? courts : Array.from(courts || []);
  if (mode === 'index') {
    return arr.length > 0 ? 'on ' + arr.join(' ') : 'on TBD';
  }
  if (arr.length === 0) return 'Court TBD';
  const prefix = arr.length === 1 ? 'Court' : 'Courts';
  return prefix + ' ' + arr.join(', ');
}

function cleanTitle(rawTitle) {
  if (!rawTitle) return '';
  const fullStr = String(rawTitle).trim();

  // 1. Explicit Skill Level Matching
  if (/intermediate[\s\-–—]+advanced/i.test(fullStr)) {
    return 'Intermediate – Advanced';
  }
  if (/adv(?:anced)?[\s_]*beginner[\s\-–—]+intermediate/i.test(fullStr)) {
    return 'Adv Beginner – Intermediate';
  }
  if (/beginner[\s\-–—]+adv(?:anced)?[\s_]*beginner/i.test(fullStr)) {
    return 'Beginner – Adv Beginner';
  }

  // 2. Segment fallback
  const segments = fullStr.split('|').map(s => s.trim()).filter(Boolean);
  let mainSegment = segments[0] || '';

  const isExcluded = /^(summer|winter|spring|fall|autumn|monday|tuesday|wednesday|thursday|friday|saturday|sunday|open\s*play)$/i;
  for (const seg of segments) {
    if (!isExcluded.test(seg)) {
      mainSegment = seg;
      break;
    }
  }

  mainSegment = mainSegment.replace(/Pickleball\s+for\s+Parkinson'?s/gi, 'P4P');
  mainSegment = mainSegment.replace(/[()]/g, '');
  mainSegment = mainSegment
    .replace(/\bSessions?\b/gi, '')
    .replace(/\bOpen\s*Play\b/gi, '')
    .replace(/\bPrime\s*Time\b/gi, '');

  mainSegment = mainSegment.replace(/[\-–—/,\s]+$/, '').replace(/\s{2,}/g, ' ').trim();
  mainSegment = mainSegment.replace(/(\d+(?:\.\d+)?)\s*[\-–—]\s*(\d+(?:\.\d+)?)/g, '$1 – $2');

  let formatted = toSentenceCase(mainSegment);
  return formatted.replace(/\bP4p\b/gi, 'P4P');
}

function resolveQueueLocation(courtsSet, customText) {
  let location = '';

  if (customText) {
    location = customText;
  } else if (courtsSet && courtsSet.size > 0) {
    const nums = Array.from(courtsSet).map(n => parseInt(n, 10)).filter(n => !isNaN(n));

    if (nums.length > 0) {
      // 1. Specific groupings for Courts 8 & 9 and Courts 10 & 12
      if (courtsSet.has('8') && courtsSet.has('9') && courtsSet.size === 2) {
        return '📍 - Court 10 Table - Left';
      }
      if (courtsSet.has('10') && courtsSet.has('12') && courtsSet.size === 2) {
        return '📍 - Court 10 Table - Right';
      }

      // 2. Both Court 4 and Court 7 are present:
      if (courtsSet.has('4') && courtsSet.has('7')) {
        if (courtsSet.has('10') || courtsSet.has('11') || courtsSet.has('12')) {
          return '📍 - Court 7 Paddle Rack';
        }
        return '📍 - Court 4 Table';
      }

      // 3. Priority groupings for 1, 2, 4 and 1, 2, 5
      if ((courtsSet.has('1') && courtsSet.has('2') && courtsSet.has('4')) ||
          (courtsSet.has('1') && courtsSet.has('2') && courtsSet.has('5'))) {
        location = 'Court 1 Paddle Rack';
      }
      // Priority 2: Exact single court assignment
      else if (nums.length === 1 && [1, 3, 6, 7, 9, 10, 11, 12].includes(nums[0])) {
        location = 'Court ' + nums[0] + ' Table';
      }
      // Priority 3: Groups containing 4 & 5 or between 4 - 6
      else if ((courtsSet.has('4') && courtsSet.has('5')) || nums.some(n => n >= 4 && n <= 6)) {
        location = 'Court 4 Table';
      }
      // Priority 4: Groups containing 7 or between 7 - 9
      else if (courtsSet.has('7') || nums.some(n => n >= 7 && n <= 9)) {
        location = 'Court 7 Paddle Rack';
      }
      // Priority 5: Courts 1 - 3
      else if (nums.some(n => n >= 1 && n <= 3)) {
        location = 'Court 1 Paddle Rack';
      }
      // Priority 6: Courts 10+
      else if (nums.some(n => n >= 10)) {
        location = 'Court 10 Paddle Rack';
      } else {
        const minCourt = Math.min(...nums);
        location = 'Court ' + minCourt + ' Paddle Rack';
      }
    }
  }

  if (!location) return '';

  const cleanLoc = location
    .replace(/^📍\s*[-–—]?\s*/i, '')
    .replace(/^queue\s+at\s+/i, '')
    .trim();

  return '📍 - ' + cleanLoc;
}

function applyCourtOverrides(eventMap, overridesList, currentMinutes) {
  if (!Array.isArray(overridesList) || overridesList.length === 0) return;

  const parseMinutes = (val) => {
    if (!val) return 0;
    const parts = String(val).trim().split(':').map(Number);
    return (parts[0] || 0) * 60 + (parts[1] || 0);
  };

  const activeOverrides = overridesList.filter(ov => {
    const sMin = parseMinutes(ov.start);
    let eMin = parseMinutes(ov.end);
    if (eMin === 0) eMin = 24 * 60;
    return currentMinutes >= sMin && currentMinutes < eMin;
  });

  activeOverrides.forEach(ov => {
    if (Array.isArray(ov.courts) && ov.courts.length > 0) {
      Object.values(eventMap).forEach(ev => {
        if (!ov.match || new RegExp(ov.match.trim(), 'i').test(ev.title)) {
          ev.courts = new Set(ov.courts.map(String).sort((a, b) => parseInt(a, 10) - parseInt(b, 10)));
        }
      });
    }
  });
}

function formatTime(isoString, isEndTime) {
  if (!isoString) return '';
  const d = new Date(isoString);
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
    return parts1[0] + ' – ' + t2;
  }
  return t1 + ' – ' + t2;
}

if (isCycling) {
  setInterval(() => {
    cycleIndex++;
    const now = new Date();
    const targetTime = new Date(now.getTime() + lookaheadMinutes * 60 * 1000);
    applyDynamicTheme(targetTime);
  }, cycleSeconds * 1000);
}
