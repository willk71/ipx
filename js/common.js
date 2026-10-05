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
    countdownVal.textContent = String(m).padStart
