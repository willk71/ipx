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
                'High Intermediate': 'highint',
                'Advanced': 'adv'
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
                      const isTierMatch = (slug && evId.endsWith(`_${slug}`)) || (ev.title && ev.title.includes(tier));
                      if (isTierMatch && Array.isArray(courts)) {
                        ev.courts = courts.map(c => `Court ${c}`);
                        ev.manualOverride = true;
                      }
                    }
                  }
                });

                if (!Array.isArray(scheduleObj.courtOverrides)) {
                  scheduleObj.courtOverrides = [];
                }
                for (const [tier, courts] of Object.entries(allocs)) {
                  if (Array.isArray(courts) && courts.length > 0) {
                    scheduleObj.courtOverrides.push({
                      match: tier,
                      start: sTime && sTime.includes('T') ? sTime.split('T')[1].substring(0, 5) : '',
                      end: '',
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
