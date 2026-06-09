export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      let response;

      if (url.pathname === "/health") {
        response = Response.json({ status: "ok" });
      } else if (url.pathname === "/api/ingest" && request.method === "POST") {
        response = await ingest(request, env);
      } else if (url.pathname === "/api/state" && request.method === "GET") {
        response = await getState(request, env);
      } else if (url.pathname === "/api/users" && request.method === "GET") {
        response = await getUsers(env);
      } else if (url.pathname === "/api/usage" && request.method === "GET") {
        response = await getUsage(request, env);
      } else if (url.pathname === "/api/events" && request.method === "GET") {
        response = await getEvents(env);
      } else {
        response = new Response("Not Found", { status: 404 });
      }

      for (const [key, value] of Object.entries(corsHeaders)) {
        response.headers.set(key, value);
      }
      return response;
    } catch (err) {
      const response = Response.json(
        { error: String(err && err.message ? err.message : err) },
        { status: 500 }
      );
      for (const [key, value] of Object.entries(corsHeaders)) {
        response.headers.set(key, value);
      }
      return response;
    }
  },
};

function checkAuth(request, env) {
  const auth = request.headers.get("Authorization");
  return auth === `Bearer ${env.INGEST_TOKEN}`;
}

async function ingest(request, env) {
  if (!checkAuth(request, env)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const recordedAt = body.recorded_at || new Date().toISOString();
  const month = Number(body.month);
  const year = Number(body.year);

  if (!month || !year) {
    return Response.json({ error: "month/year is required" }, { status: 400 });
  }

  const managedUsers = body.managed_users || [];
  const apiKeys = body.api_keys || [];
  const result = body.result || {};
  const events = body.events || [];

  for (const user of managedUsers) {
    await env.DB.prepare(`
      INSERT INTO managed_users
        (name, budget_limit, warning_threshold, status, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?)
      ON CONFLICT(name) DO UPDATE SET
        budget_limit = excluded.budget_limit,
        warning_threshold = excluded.warning_threshold,
        updated_at = excluded.updated_at
    `).bind(
      user.name,
      user.budget_limit ?? 100,
      user.warning_threshold ?? 80,
      user.status || "active",
      recordedAt,
      recordedAt
    ).run();
  }

  for (const key of apiKeys) {
    const identity = `${key.user_name}|${key.sensitive_id || ""}|${key.platform_created_at || ""}`;

    await env.DB.prepare(`
      INSERT INTO api_keys
        (api_key_identity, user_name, sensitive_id, redacted_key, platform_created_at, status, first_seen_at, last_seen_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(api_key_identity) DO UPDATE SET
        redacted_key = excluded.redacted_key,
        last_seen_at = excluded.last_seen_at
    `).bind(
      identity,
      key.user_name,
      key.sensitive_id || "",
      key.redacted_key || "",
      key.platform_created_at || "",
      key.status || "active",
      recordedAt,
      recordedAt
    ).run();
  }

  for (const [user, info] of Object.entries(result.users || {})) {
    const key = apiKeys.find(k => k.user_name === user);
    const apiKeyIdentity = key
      ? `${key.user_name}|${key.sensitive_id || ""}|${key.platform_created_at || ""}`
      : "";

    await env.DB.prepare(`
      INSERT INTO usage_records
        (recorded_at, month, year, user_name, api_key, api_key_identity, cost, tokens, requests, models_info, status)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).bind(
      recordedAt,
      month,
      year,
      user,
      info.api_key || "",
      apiKeyIdentity,
      Number(info.cost || 0),
      Number(info.tokens || 0),
      Number(info.requests || 0),
      JSON.stringify(info.models || {}),
      "active"
    ).run();
  }

  for (const event of events) {
    await env.DB.prepare(`
      INSERT INTO events
        (created_at, user_name, api_key_identity, event_type, reason, cost, tokens, requests, payload)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).bind(
      event.created_at || recordedAt,
      event.user_name,
      event.api_key_identity || "",
      event.event_type,
      event.reason || "",
      Number(event.cost || 0),
      Number(event.tokens || 0),
      Number(event.requests || 0),
      JSON.stringify(event.payload || {})
    ).run();

    if (event.event_type === "block" || event.event_type === "delete_api") {
      await env.DB.prepare(`
        UPDATE managed_users
        SET status = 'blocked', updated_at = ?
        WHERE name = ?
      `).bind(recordedAt, event.user_name).run();

      if (event.api_key_identity) {
        await env.DB.prepare(`
          UPDATE api_keys
          SET status = 'used',
              deleted_at = ?,
              final_cost = ?,
              final_tokens = ?,
              final_requests = ?
          WHERE api_key_identity = ?
        `).bind(
          recordedAt,
          Number(event.cost || 0),
          Number(event.tokens || 0),
          Number(event.requests || 0),
          event.api_key_identity
        ).run();
      }
    }
  }

  return Response.json({
    ok: true,
    users: Object.keys(result.users || {}).length,
    api_keys: apiKeys.length,
    events: events.length,
  });
}

async function getState(request, env) {
  if (!checkAuth(request, env)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const usersResult = await env.DB.prepare(`
    SELECT name, budget_limit, warning_threshold, status
    FROM managed_users
  `).all();

  const eventsResult = await env.DB.prepare(`
    SELECT user_name, api_key_identity, event_type
    FROM events
    WHERE event_type IN ('warning', 'block', 'delete_api')
    ORDER BY created_at DESC
    LIMIT 1000
  `).all();

  const users = {};
  for (const user of usersResult.results || []) {
    users[user.name] = user;
  }

  return Response.json({
    users,
    events: eventsResult.results || [],
  });
}

async function getUsers(env) {
  const { results } = await env.DB.prepare(`
    SELECT
      m.name,
      m.budget_limit,
      m.warning_threshold,
      m.status,
      u.cost,
      u.tokens,
      u.requests,
      u.recorded_at
    FROM managed_users m
    LEFT JOIN usage_records u
      ON u.id = (
        SELECT id
        FROM usage_records
        WHERE user_name = m.name
        ORDER BY recorded_at DESC
        LIMIT 1
      )
    ORDER BY COALESCE(u.cost, 0) DESC
  `).all();

  return Response.json(results);
}

async function getUsage(request, env) {
  const url = new URL(request.url);
  const user = url.searchParams.get("user");
  const limit = Number(url.searchParams.get("limit") || "100");

  if (!user) {
    return Response.json({ error: "user is required" }, { status: 400 });
  }

  const { results } = await env.DB.prepare(`
    SELECT *
    FROM usage_records
    WHERE user_name = ?
    ORDER BY recorded_at DESC
    LIMIT ?
  `).bind(user, limit).all();

  return Response.json(results);
}

async function getEvents(env) {
  const { results } = await env.DB.prepare(`
    SELECT *
    FROM events
    ORDER BY created_at DESC
    LIMIT 100
  `).all();

  return Response.json(results);
}
