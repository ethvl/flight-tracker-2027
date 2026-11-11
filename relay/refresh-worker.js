/**
 * Refresh relay for the flight tracker (Cloudflare Worker, free plan is enough).
 *
 * The dashboard is a static GitHub Pages site, so its "Refresh Fares" button cannot
 * start a fetch itself, and a GitHub key must never be placed in a public page.
 * This worker holds the key and starts the repository's fare-fetch workflow.
 *
 * Settings (Worker -> Settings -> Variables and secrets):
 *   GITHUB_TOKEN    secret  fine-grained token: this repository only, "Actions: Read and write"
 *   REPO            text    ethvl/flight-tracker-2027
 *   WORKFLOW        text    daily.yml
 *   ALLOWED_ORIGIN  text    https://ethvl.github.io
 *   MIN_MINUTES     text    15   (minimum gap between fetches; each fetch costs up to 24 SerpAPI searches)
 *
 * POST /refresh  ->  {"status": "started" | "running" | "fresh", "next_allowed": ISO time?}
 */
export default {
  async fetch(request, env) {
    const origin = env.ALLOWED_ORIGIN || "";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Vary": "Origin",
    };
    const reply = (body, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return reply({ status: "error", message: "Use POST" }, 405);
    if (origin && request.headers.get("Origin") !== origin) return reply({ status: "error", message: "Origin not allowed" }, 403);

    const api = `https://api.github.com/repos/${env.REPO}/actions/workflows/${env.WORKFLOW || "daily.yml"}`;
    const gh = (path, init = {}) =>
      fetch(api + path, {
        ...init,
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "flight-tracker-refresh",
          "X-GitHub-Api-Version": "2022-11-28",
          ...(init.headers || {}),
        },
      });

    // 1. A fetch already queued or running: don't start another one.
    const runs = await gh("/runs?per_page=5");
    if (!runs.ok) return reply({ status: "error", message: `GitHub returned ${runs.status}` }, 502);
    const list = (await runs.json()).workflow_runs || [];
    if (list.some((r) => r.status !== "completed")) return reply({ status: "running" });

    // 2. Rate limit: protects the SerpAPI quota from repeated clicks by any visitor.
    const gapMs = Number(env.MIN_MINUTES || 15) * 60_000;
    const last = list[0] ? Date.parse(list[0].created_at) : 0;
    if (Date.now() - last < gapMs) return reply({ status: "fresh", next_allowed: new Date(last + gapMs).toISOString() });

    // 3. Start a fresh fetch + redeploy.
    const go = await gh("/dispatches", { method: "POST", body: JSON.stringify({ ref: "main" }) });
    if (go.status !== 204) return reply({ status: "error", message: `GitHub returned ${go.status}` }, 502);
    return reply({ status: "started" });
  },
};
