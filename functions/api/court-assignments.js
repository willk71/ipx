// Cloudflare Pages Function: /api/court-assignments
// Provides high-speed edge read/write for manual court overrides stored in Cloudflare KV (IPX_DATA).

export async function onRequest(context) {
  const { request, env } = context;
  const method = request.method.toUpperCase();

  // CORS headers
  const corsHeaders = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400"
  };

  if (method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  const KV_KEY = "manual_court_assignments";

  // --- GET: Retrieve active manual court assignments ---
  if (method === "GET") {
    try {
      if (env.IPX_DATA) {
        const raw = await env.IPX_DATA.get(KV_KEY);
        if (raw) {
          return new Response(raw, {
            headers: {
              "Content-Type": "application/json; charset=utf-8",
              "Cache-Control": "no-cache, no-store, must-revalidate",
              "X-Data-Source": "cloudflare-kv",
              ...corsHeaders
            }
          });
        }
      }
    } catch (err) {
      console.error("KV read error for manual_court_assignments:", err);
    }

    // Default empty structure
    return new Response(
      JSON.stringify({
        lastUpdated: null,
        sessions: {}
      }),
      {
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-cache, no-store, must-revalidate",
          ...corsHeaders
        }
      }
    );
  }

  // --- POST / PUT: Save or reset manual court assignments for a session ---
  if (method === "POST" || method === "PUT") {
    try {
      if (!env.IPX_DATA) {
        return new Response(
          JSON.stringify({ success: false, error: "Cloudflare KV IPX_DATA binding not found." }),
          { status: 500, headers: { "Content-Type": "application/json", ...corsHeaders } }
        );
      }

      const payload = await request.json();
      const sessionKey = payload.sessionKey; // e.g. "2160558_2026-11-11T11:00:00" or title/date
      if (!sessionKey) {
        return new Response(
          JSON.stringify({ success: false, error: "Missing required 'sessionKey' field." }),
          { status: 400, headers: { "Content-Type": "application/json", ...corsHeaders } }
        );
      }

      // Fetch existing overrides store
      let currentData = { lastUpdated: null, sessions: {} };
      try {
        const rawExisting = await env.IPX_DATA.get(KV_KEY);
        if (rawExisting) {
          currentData = JSON.parse(rawExisting);
          if (!currentData.sessions) currentData.sessions = {};
        }
      } catch (e) {
        console.warn("Notice: Initializing fresh manual_court_assignments store:", e);
      }

      const nowIso = new Date().toISOString();

      if (payload.reset === true) {
        // Reset/remove manual overrides for this specific session
        delete currentData.sessions[sessionKey];
      } else {
        // Save manual allocations and individual court statuses
        currentData.sessions[sessionKey] = {
          sessionKey: sessionKey,
          eventId: payload.eventId || "",
          title: payload.title || "",
          startTime: payload.startTime || "",
          allocations: payload.allocations || {}, // { "Advanced": ["11", "12"], ... }
          courtStatus: payload.courtStatus || {}, // { "1": "Intermediate", "2": "Private", ... }
          author: payload.author || "Staff",
          updatedAt: nowIso
        };
      }

      currentData.lastUpdated = nowIso;

      // Persist to Cloudflare KV (30 day TTL or permanent)
      await env.IPX_DATA.put(KV_KEY, JSON.stringify(currentData), {
        metadata: { lastUpdated: nowIso }
      });

      return new Response(
        JSON.stringify({
          success: true,
          action: payload.reset ? "reset" : "saved",
          sessionKey: sessionKey,
          timestamp: nowIso,
          data: currentData.sessions[sessionKey] || null
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            ...corsHeaders
          }
        }
      );
    } catch (err) {
      console.error("Error saving manual court assignment:", err);
      return new Response(
        JSON.stringify({ success: false, error: err.message }),
        { status: 500, headers: { "Content-Type": "application/json", ...corsHeaders } }
      );
    }
  }

  return new Response("Method Not Allowed", { status: 405, headers: corsHeaders });
}
