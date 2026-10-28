export async function onRequest(context) {
  try {
    // 1. Try reading live schedule from Cloudflare KV
    if (context.env.IPX_DATA) {
      const kvData = await context.env.IPX_DATA.get("schedule_latest");
      if (kvData) {
        return new Response(kvData, {
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "public, max-age=10, s-maxage=10",
            "Access-Control-Allow-Origin": "*",
            "X-Data-Source": "cloudflare-kv"
          }
        });
      }
    }
  } catch (err) {
    console.error("KV read error for schedule_latest:", err);
  }

  // 2. Seamless fallback to static data/schedule.json
  const fallbackUrl = new URL("/data/schedule.json", context.request.url);
  return context.env.ASSETS.fetch(fallbackUrl);
}
