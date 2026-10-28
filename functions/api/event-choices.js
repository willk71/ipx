export async function onRequest(context) {
  try {
    // 1. Try reading live choices breakdown from Cloudflare KV
    if (context.env.IPX_DATA) {
      const kvData = await context.env.IPX_DATA.get("event_choices_latest");
      if (kvData) {
        return new Response(kvData, {
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=30, s-maxage=30",
            "Access-Control-Allow-Origin": "*",
            "X-Data-Source": "cloudflare-kv"
          }
        });
      }
    }
  } catch (err) {
    console.error("KV read error for event_choices_latest:", err);
  }

  // 2. Seamless fallback to static data/event-choices.json
  const fallbackUrl = new URL("/data/event-choices.json", context.request.url);
  return context.env.ASSETS.fetch(fallbackUrl);
}
