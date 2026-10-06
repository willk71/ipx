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
const timeParam = urlParams.get('time');

function parseExplicitTime(timeStr, baseDate) {
  if (!timeStr) return null;
  const str = timeStr.trim().toUpperCase();
  const match = str.match(/^(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?$/i);
  if (!match) return null;

  let hours = parseInt(match[1], 10);
  const minutes = match[2] ? parseInt(match[2], 10) : 0;
  const meridian = match[3];

  if (meridian === 'PM' && hours < 12) hours += 12;
  if (meridian === 'AM' && hours === 12) hours = 0;

  const target = new Date(baseDate || new Date());
  target.setHours(hours, minutes, 0, 0);
  return target;
}

const explicitTargetDate = parseExplicitTime(timeParam, new Date());
const hasExplicitAhead = urlParams.has('ahead');
const isNamed60 = window.location.pathname.includes('60');
const defaultAhead = isNamed60 ? '60' : '15';
const lookaheadMinutes = parseInt(urlParams.get('ahead') || defaultAhead, 10);
const isPreview = explicitTargetDate !== null || (hasExplicitAhead && lookaheadMinutes !== 15);

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
      const day = targetTime.getDay(); // 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
      const isTTh = (day === 2 || day === 4);
      const totalMinutes = targetTime.getHours() * 60 + targetTime.getMinutes();
      
      // We define the targetTime boundaries (which occur 15 mins before real-time session starts)
      let boundaries;
      if (isTTh) {
        // T/Th: 7AM, 9AM, 11AM, 2PM (14:00), 4PM (16:00), 6PM (18:00), 8PM (20:00), 10PM (22:00)
        boundaries = [420, 540, 660, 840, 960, 1080, 1200, 1320];
      } else {
        // M/W/F/S/S: 7AM, 9AM, 11AM, 1:30PM (13:30), 3:30PM (15:30), 5:30PM (17:30), 7:30PM (19:30), 9:30PM (21:30)
        boundaries = [420, 540, 660, 810, 930, 1050, 1170, 1290];
      }
      
      const themeSchedule = [
        'theme-stealth',    // Before 7AM
        'theme-tiffany',    // Slot 1
        'theme-usopen',     // Slot 2
        'theme-apple',      // Slot 3
        'theme-rolex',      // Slot 4
        'theme-porsche',    // Slot 5
        'theme-wimbledon',  // Slot 6
        'theme-vice',       // Slot 7
        'theme-cyberpunk'   // Slot 8 (Late night)
      ];

      let slotIndex = 0;
      for (let i = 0; i < boundaries.length; i++) {
        if (totalMinutes >= boundaries[i]) {
          slotIndex = i + 1;
        }
      }
      
      themeToApply = themeSchedule[slotIndex] || 'theme-apple';
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
    .replace(/\bPrime\s*Time\b/gi);

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
      // Courts 2, 3, 5, 6 queue at Court 6 Paddle Rack
      const court6Group = [2, 3, 5, 6];
      if (nums.every(n => court6Group.includes(n))) {
        return '📍 - Court 6 Paddle Rack';
      }

      // Explicit 2-court pair rules
      if (courtsSet.has('6') && courtsSet.has('9') && courtsSet.size === 2) {
        return '📍 - Court 6 Paddle Rack';
      }
      if (courtsSet.has('9') && courtsSet.has('11') && courtsSet.size === 2) {
        return '📍 - Court 9 Paddle Rack';
      }
      if (courtsSet.has('3') && courtsSet.has('6') && courtsSet.size === 2) {
        return '📍 - Court 6 Paddle Rack';
      }
      if (
        (courtsSet.has('8') && courtsSet.has('9') && courtsSet.size === 2) ||
        (courtsSet.has('9') && courtsSet.has('10') && courtsSet.size === 2)
      ) {
        return '📍 - Court 10 Table - Left';
      }
      if (
        (courtsSet.has('10') && courtsSet.has('12') && courtsSet.size === 2) ||
        (courtsSet.has('11') && courtsSet.has('12') && courtsSet.size === 2)
      ) {
        return '📍 - Court 10 Table - Right';
      }

      // Both Court 4 and Court 7 are present:
      if (courtsSet.has('4') && courtsSet.has('7')) {
        if (courtsSet.has('10') || courtsSet.has('11') || courtsSet.has('12')) {
          return '📍 - Court 7 Paddle Rack';
        }
        return '📍 - Court 4 Table';
      }

      // Priority groupings for 1 and 4
      if (courtsSet.has('1') && courtsSet.has('4')) {
        location = 'Court 1 Paddle Rack';
      }
      // Exact single court assignment
      else if (nums.length === 1) {
        if ([2, 3, 5, 6].includes(nums[0])) {
          location = 'Court 6 Paddle Rack';
        } else if ([1, 4, 7, 9, 10, 11, 12].includes(nums[0])) {
          location = 'Court ' + nums[0] + ' Table';
        }
      }
      // Groups containing 4
      else if (courtsSet.has('4')) {
        location = 'Court 4 Table';
      }
      // Groups containing 7 or between 7 - 9
      else if (courtsSet.has('7') || nums.some(n => n >= 7 && n <= 9)) {
        location = 'Court 7 Paddle Rack';
      }
      // Court 1 fallback
      else if (courtsSet.has('1')) {
        location = 'Court 1 Paddle Rack';
      }
      // Priority 6: Courts 10+
      else if (nums.some(n => n >= 10)) {
        location = 'Court 10 Paddle Rack';
      } else {
        const minCourt = Math.min(...nums);
        location = [2, 3, 5, 6].includes(minCourt) ? 'Court 6 Paddle Rack' : 'Court ' + minCourt + ' Paddle Rack';
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
    const baseDate = explicitTargetDate ? new Date(explicitTargetDate) : now;
    const targetTime = new Date(baseDate.getTime() + (urlParams.has('time') && !urlParams.has('ahead') ? 0 : lookaheadMinutes * 60 * 1000));
    applyDynamicTheme(targetTime);
  }, cycleSeconds * 1000);
}
