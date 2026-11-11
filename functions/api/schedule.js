export async function onRequest(context) {
  try {
    // 1. Try reading live schedule from Cloudflare KV
    if (context.env.IPX_DATA) {
      const kvData = await context.env.IPX_DATA.get("schedule_latest");
      if (kvData) {
        let scheduleObj;
        try {
          scheduleObj = JSON.parse(kvData);
        } catch (_) {
          scheduleObj = null;
        }

        // Check if manual court assignments exist to merge in real-time
        if (scheduleObj) {
          try {
            const rawManual = await context.env.IPX_DATA.get("manual_court_assignments");
            if (rawManual) {
              const manualData = JSON.parse(rawManual);
              const manualSessions = manualData.sessions || {};

              const groupSlugs = {
                'Advanced Beginner': 'advbeg',
                'Intermediate': 'int',
                'Intermediate+': 'int',
                'High Intermediate': 'highint',
                'High Intermediate+': 'highint',
                'Advanced': 'adv',
                'Novice / Beginner': 'novice',
                'Novice/Beginner': 'novice',
                'Drilling': 'drilling',
                'Clinic': 'clinic'
              };

              const matchesTierStrict = (title, matchStr) => {
                if (!matchStr) return true;
                const t = String(title || '').toLowerCase();
                const m = String(matchStr).toLowerCase().trim();
                if (m === 'high intermediate' || m === 'high int' || m === 'high intermediate+' || m === 'high int+') {
                  return /\bhigh\s*intermediate\b/.test(t) || /\bhigh\s*int\b/.test(t) || /\bhigh\b/.test(t);
                }
                if (m === 'intermediate' || m === 'int' || m === 'intermediate+' || m === 'int+') {
                  return (/\bintermediate\b/.test(t) || /\bint\b/.test(t)) && !/\bhigh\b/.test(t);
                }
                if (m === 'advanced beginner' || m === 'adv beg' || m === 'advbeg') {
                  return /\b(advanced|adv)\s*beginner\b/.test(t) || /\badvbeg\b/.test(t);
                }
                if (m === 'novice / beginner' || m === 'novice/beginner' || m === 'novice' || m === 'beginner') {
                  return /\bnovice\b/.test(t) || (/\bbeginner\b/.test(t) && !/\badv(?:anced)?\b/.test(t));
                }
                if (m === 'drilling' || m === 'drill') {
                  return /\bdrill(?:ing)?\b/.test(t);
                }
                if (m === 'clinic' || m === 'clinics') {
                  return /\bclinic[s]?\b/.test(t);
                }
                if (m === 'advanced' || m === 'adv') {
                  return (/\badvanced\b/.test(t) || /\badv\b/.test(t)) && !/\bbeginner\b/.test(t) && !/\bbeg\b/.test(t);
                }
                return new RegExp('\\b' + m.replace(/[+*?^$(){}|[\]\\]/g, '\\$&') + '\\b', 'i').test(t);
              };

              Object.values(manualSessions).forEach(man => {
                const eId = String(man.eventId || '').trim();
                const sTime = String(man.startTime || '').trim();
                const allocs = man.allocations || {};

                (scheduleObj.events || []).forEach(ev => {
                  const evId = String(ev.eventId || '').trim();
                  const evStart = String(ev.startTime || '').trim();
                  const matchesId = eId && (evId === eId || evId.startsWith(`${eId}_`));
                  const matchesTime = !sTime || evStart === sTime;

                  if (matchesId && matchesTime) {
                    for (const [tier, courts] of Object.entries(allocs)) {
                      const slug = groupSlugs[tier] || '';
                      const isTierMatch = (slug && evId.endsWith(`_${slug}`)) || matchesTierStrict(ev.title, tier);
                      if (isTierMatch && Array.isArray(courts)) {
                        ev.courts = courts.map(c => `Court ${c}`);
                        ev.manualOverride = true;
                      }
                    }
                  }
                });

                // Determine session end time to prevent overrides from persisting beyond their session window
                let endStr = '';
                if (man.endTime && man.endTime.includes('T')) {
                  endStr = man.endTime.split('T')[1].substring(0, 5);
                } else {
                  const matchEv = (scheduleObj.events || []).find(ev => {
                    const evId = String(ev.eventId || '').trim();
                    const evStart = String(ev.startTime || '').trim();
                    return eId && (evId === eId || evId.startsWith(`${eId}_`)) && (!sTime || evStart === sTime);
                  });
                  if (matchEv && matchEv.endTime && matchEv.endTime.includes('T')) {
                    endStr = matchEv.endTime.split('T')[1].substring(0, 5);
                  } else if (sTime && sTime.includes('T')) {
                    const parts = sTime.split('T')[1].substring(0, 5).split(':').map(Number);
                    const endMin = (parts[0] || 0) * 60 + (parts[1] || 0) + 120;
                    const h = Math.floor(endMin / 60) % 24;
                    const m = endMin % 60;
                    endStr = `${h < 10 ? '0' : ''}${h}:${m < 10 ? '0' : ''}${m}`;
                  }
                }

                if (!Array.isArray(scheduleObj.courtOverrides)) {
                  scheduleObj.courtOverrides = [];
                }
                for (const [tier, courts] of Object.entries(allocs)) {
                  if (Array.isArray(courts) && courts.length > 0) {
                    scheduleObj.courtOverrides.push({
                      match: tier,
                      start: sTime && sTime.includes('T') ? sTime.split('T')[1].substring(0, 5) : '',
                      end: endStr,
                      courts: courts
                    });
                  }
                }
              });
            }
          } catch (mErr) {
            console.warn("Notice: Error merging manual court assignments:", mErr);
          }

          return new Response(JSON.stringify(scheduleObj), {
            headers: {
              "Content-Type": "application/json; charset=utf-8",
              "Cache-Control": "public, max-age=5, s-maxage=5",
              "Access-Control-Allow-Origin": "*",
              "X-Data-Source": "cloudflare-kv-merged"
            }
          });
        }
      }
    }
  } catch (err) {
    console.error("KV read error for schedule_latest:", err);
  }

  // 2. Seamless fallback to static data/schedule.json
  const fallbackUrl = new URL("/data/schedule.json", context.request.url);
  return context.env.ASSETS.fetch(fallbackUrl);
}
