// Automatically connect to the same IP hosting the dashboard
const MQTT_BROKER_URL = `ws://${window.location.hostname}:9001`;
const MQTT_TOPIC = 'zigbee2mqtt/+'; // Subscribe to all zigbee2mqtt devices

// Mapping of action strings to alert messages
// Update these based on your specific remote's payloads
const ACTION_MAP = {
  '1_single': 'NEEDS 1 PLAYER',
  '2_single': 'NEEDS 2 PLAYERS',
  '3_single': 'NEEDS 3 PLAYERS',
  '4_single': 'NEEDS 4 PLAYERS'
};

const CLEAR_ACTIONS = ['clear', 'off', 'stop']; // Add any actions that should clear the alert

let alertTimeout = null;
let audioObj = null;

function initMqttAlerts() {
  // Inject CSS for the alert overlay
  const style = document.createElement('style');
  style.textContent = `
    #global-mqtt-alert {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(200, 0, 0, 0.95);
      z-index: 9999;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      text-align: center;
      color: white;
      animation: flash-bg 2s infinite alternate;
      backdrop-filter: blur(10px);
    }
    
    @keyframes flash-bg {
      0% { background: rgba(220, 20, 20, 0.95); }
      100% { background: rgba(150, 0, 0, 0.95); }
    }

    #mqtt-alert-title {
      font-size: clamp(4rem, 8vw, 8rem);
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 2vh;
      text-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }

    #mqtt-alert-message {
      font-size: clamp(3rem, 6vw, 6rem);
      font-weight: 700;
      color: #ffd60a;
      margin-bottom: 6vh;
      text-shadow: 0 5px 20px rgba(0,0,0,0.5);
    }

    #mqtt-alert-ack {
      padding: 3vh 6vw;
      font-size: clamp(2rem, 4vw, 4rem);
      font-weight: 800;
      background: #ffffff;
      color: #cc0000;
      border: none;
      border-radius: 20px;
      cursor: pointer;
      box-shadow: 0 10px 30px rgba(0,0,0,0.4);
      transition: transform 0.1s;
    }
    
    #mqtt-alert-ack:active {
      transform: scale(0.95);
    }
  `;
  document.head.appendChild(style);

  // Create overlay DOM
  const overlay = document.createElement('div');
  overlay.id = 'global-mqtt-alert';
  overlay.innerHTML = `
    <div id="mqtt-alert-title">Court Alert</div>
    <div id="mqtt-alert-message">Needs Players</div>
    <button id="mqtt-alert-ack">ACKNOWLEDGE</button>
  `;
  document.body.appendChild(overlay);

  overlay.querySelector('#mqtt-alert-ack').addEventListener('click', closeAlert);

  // Create Audio
  // Using a standard modern notification chime URL, you can replace with a local file path like 'audio/chime.mp3'
  audioObj = new Audio('https://actions.google.com/sounds/v1/alarms/spaceship_alarm.ogg');
  audioObj.loop = true;

  // Connect to MQTT
  if (typeof mqtt !== 'undefined') {
    const client = mqtt.connect(MQTT_BROKER_URL);

    client.on('connect', () => {
      console.log('✅ Connected to MQTT Broker for alerts');
      client.subscribe(MQTT_TOPIC);
    });

    client.on('error', (err) => {
      console.error('❌ MQTT Connection Error:', err);
    });

    client.on('message', (topic, message) => {
      console.log(`📩 Received MQTT message on [${topic}]:`, message.toString());
      try {
        const payload = JSON.parse(message.toString());
        
        let courtName = 'Unknown Court';
        const match = topic.match(/court_(\d+)/i);
        if (match) {
          courtName = 'Court ' + match[1];
        }

        console.log(`🔍 Extracted Court: ${courtName} | Current Tablet Filter: ${window.currentTabletFilter || 'NONE'}`);

        // If this tablet is filtered to a specific queue, only flash if the court matches
        if (window.currentTabletFilter && courtName !== 'Unknown Court') {
          if (!window.currentTabletFilter.includes(courtName.toLowerCase())) {
            console.log(`🚫 Ignored alert: Tablet is filtered for ${window.currentTabletFilter}, but alert was for ${courtName}`);
            return; // Ignore this alert, it's for a different court
          }
        }

        if (payload.action) {
          console.log(`⚡ Action triggered: ${payload.action}`);
          if (CLEAR_ACTIONS.includes(payload.action) || payload.action === '3_single') {
            closeAlert();
          } else if (ACTION_MAP[payload.action]) {
            showAlert(courtName, ACTION_MAP[payload.action]);
          } else if (payload.action === '1_single') {
            // Fallback for user snippet
            showAlert(courtName, '⚠️ NEED 1 PLAYER');
          } else {
            console.log(`🤷 Unknown action: ${payload.action}`);
          }
        }
      } catch (e) {
        console.error('❌ Failed to parse MQTT message', e);
      }
    });
  } else {
    console.error('MQTT.js library not loaded');
  }
}

function showAlert(title, message) {
  const overlay = document.getElementById('global-mqtt-alert');
  document.getElementById('mqtt-alert-title').innerText = title;
  document.getElementById('mqtt-alert-message').innerText = message;
  
  overlay.style.display = 'flex';
  
  // Play sound
  if (audioObj) {
    audioObj.currentTime = 0;
    audioObj.play().catch(e => console.log('Audio autoplay blocked', e));
  }

  // Auto close timer
  if (alertTimeout) clearTimeout(alertTimeout);
  alertTimeout = setTimeout(() => {
    closeAlert();
  }, 30000);
}

function closeAlert() {
  const overlay = document.getElementById('global-mqtt-alert');
  if (overlay) overlay.style.display = 'none';
  if (audioObj) {
    audioObj.pause();
    audioObj.currentTime = 0;
  }
  if (alertTimeout) {
    clearTimeout(alertTimeout);
    alertTimeout = null;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initMqttAlerts);
} else {
  initMqttAlerts();
}

