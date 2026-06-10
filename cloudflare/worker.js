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
        response = await getUsers(request, env);
      } else if (url.pathname === "/api/usage" && request.method === "GET") {
        response = await getUsage(request, env);
      } else if (url.pathname === "/api/events" && request.method === "GET") {
        response = await getEvents(request, env);
      } else if (url.pathname === "/api/api-keys" && request.method === "GET") {
        response = await getApiKeys(request, env);
      } else if (url.pathname === "/api/summary" && request.method === "GET") {
        response = await getSummary(request, env);
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

function isAuthorized(request, env) {
  const auth = request.headers.get("Authorization");
  return auth === `Bearer ${env.INGEST_TOKEN}`;
}

function requireAuth(request, env) {
  if (!isAuthorized(request, env)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  return null;
}

function normalizeApiKeyIdentity(key) {
  if (key.api_key_identity) {
    return key.api_key_identity;
  }
  return `${key.user_name}|${key.sensitive_id || ""}|${key.platform_created_at || ""}`;
}

function parseOptionalNumber(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseLimit(url, fallback = 100, max = 500) {
  const parsed = Number(url.searchParams.get("limit") || String(fallback));
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.min(Math.floor(parsed), max);
}

function parseJsonValue(value, fallback) {
  if (!value) {
    return fallback;
  }
  try {
    return JSON.parse(value);
  } catch (_err) {
    return fallback;
  }
}

function mapUsageRecord(record) {
  return {
    ...record,
    models_info: parseJsonValue(record.models_info, {}),
    api_keys_info: parseJsonValue(record.api_keys_info, []),
    active_key_identities: parseJsonValue(record.active_key_identities, []),
  };
}

function mapEventRecord(record) {
  return {
    ...record,
    payload: parseJsonValue(record.payload, {}),
  };
}

function itemsResponse(items, extra = {}) {
  return Response.json({
    ...extra,
    items,
    total: items.length,
  });
}

async function ingest(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
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
        status = excluded.status,
        updated_at = excluded.updated_at
    `).bind(
      user.name,
      Number(user.budget_limit ?? 100),
      Number(user.warning_threshold ?? 80),
      user.status || "active",
      recordedAt,
      recordedAt
    ).run();
  }

  for (const key of apiKeys) {
    const identity = normalizeApiKeyIdentity(key);
    if (!identity) {
      continue;
    }

    await env.DB.prepare(`
      INSERT INTO api_keys
        (
          api_key_identity,
          user_name,
          sensitive_id,
          redacted_key,
          platform_created_at,
          status,
          first_seen_at,
          last_seen_at,
          deleted_at,
          final_cost,
          final_tokens,
          final_requests
        )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(api_key_identity) DO UPDATE SET
        user_name = excluded.user_name,
        sensitive_id = excluded.sensitive_id,
        redacted_key = excluded.redacted_key,
        platform_created_at = excluded.platform_created_at,
        status = CASE
          WHEN excluded.status = 'used' THEN 'used'
          ELSE excluded.status
        END,
        last_seen_at = excluded.last_seen_at,
        deleted_at = COALESCE(excluded.deleted_at, api_keys.deleted_at),
        final_cost = CASE
          WHEN excluded.status = 'used' THEN excluded.final_cost
          ELSE api_keys.final_cost
        END,
        final_tokens = CASE
          WHEN excluded.status = 'used' THEN excluded.final_tokens
          ELSE api_keys.final_tokens
        END,
        final_requests = CASE
          WHEN excluded.status = 'used' THEN excluded.final_requests
          ELSE api_keys.final_requests
        END
    `).bind(
      identity,
      key.user_name,
      key.sensitive_id || "",
      key.redacted_key || "",
      key.platform_created_at || "",
      key.status || "active",
      recordedAt,
      recordedAt,
      key.deleted_at || null,
      Number(key.final_cost || 0),
      Number(key.final_tokens || 0),
      Number(key.final_requests || 0)
    ).run();
  }

  for (const [userName, info] of Object.entries(result.users || {})) {
    const activeKeyIdentities = (info.active_api_keys || [])
      .map((key) => key.api_key_identity)
      .filter(Boolean);

    await env.DB.prepare(`
      INSERT INTO usage_records
        (
          recorded_at,
          month,
          year,
          user_name,
          cost,
          tokens,
          requests,
          models_info,
          api_keys_info,
          active_key_identities,
          status
        )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).bind(
      recordedAt,
      month,
      year,
      userName,
      Number(info.cost || 0),
      Number(info.tokens || 0),
      Number(info.requests || 0),
      JSON.stringify(info.models || {}),
      JSON.stringify(info.api_keys || []),
      JSON.stringify(activeKeyIdentities),
      "observed"
    ).run();
  }

  for (const event of events) {
    await env.DB.prepare(`
      INSERT INTO events
        (
          event_key,
          created_at,
          month,
          year,
          period_key,
          user_name,
          api_key_identity,
          event_type,
          reason,
          cost,
          tokens,
          requests,
          payload
        )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(event_key) DO UPDATE SET
        created_at = excluded.created_at,
        reason = excluded.reason,
        cost = excluded.cost,
        tokens = excluded.tokens,
        requests = excluded.requests,
        payload = excluded.payload
    `).bind(
      event.event_key,
      event.created_at || recordedAt,
      Number(event.month || month),
      Number(event.year || year),
      event.period_key || `${year}-${String(month).padStart(2, "0")}`,
      event.user_name,
      event.api_key_identity || "",
      event.event_type,
      event.reason || "",
      Number(event.cost || 0),
      Number(event.tokens || 0),
      Number(event.requests || 0),
      JSON.stringify(event.payload || {})
    ).run();
  }

  return Response.json({
    ok: true,
    users: Object.keys(result.users || {}).length,
    api_keys: apiKeys.length,
    events: events.length,
  });
}

async function getState(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const usersResult = await env.DB.prepare(`
    SELECT name, budget_limit, warning_threshold, status
    FROM managed_users
  `).all();

  const eventsResult = await env.DB.prepare(`
    SELECT event_key, user_name, api_key_identity, event_type, month, year, period_key
    FROM events
    WHERE event_type IN ('warning', 'block', 'delete_api')
    ORDER BY created_at DESC
    LIMIT 2000
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

async function getUsers(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const url = new URL(request.url);
  const status = url.searchParams.get("status");
  const binds = [];
  const whereClause = status ? "WHERE m.status = ?" : "";
  if (status) {
    binds.push(status);
  }

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
    ${whereClause}
    ORDER BY COALESCE(u.cost, 0) DESC
  `).bind(...binds).all();

  return itemsResponse(results || []);
}

async function getUsage(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const url = new URL(request.url);
  const user = url.searchParams.get("user");
  const limit = parseLimit(url, 100, 1000);
  const month = parseOptionalNumber(url.searchParams.get("month"));
  const year = parseOptionalNumber(url.searchParams.get("year"));

  if (!user) {
    return Response.json({ error: "user is required" }, { status: 400 });
  }

  const conditions = ["user_name = ?"];
  const binds = [user];
  if (month !== null) {
    conditions.push("month = ?");
    binds.push(month);
  }
  if (year !== null) {
    conditions.push("year = ?");
    binds.push(year);
  }
  binds.push(limit);

  const { results } = await env.DB.prepare(`
    SELECT *
    FROM usage_records
    WHERE ${conditions.join(" AND ")}
    ORDER BY recorded_at DESC
    LIMIT ?
  `).bind(...binds).all();

  return itemsResponse((results || []).map(mapUsageRecord), {
    user,
    month,
    year,
  });
}

async function getEvents(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const url = new URL(request.url);
  const user = url.searchParams.get("user");
  const eventType = url.searchParams.get("event_type");
  const month = parseOptionalNumber(url.searchParams.get("month"));
  const year = parseOptionalNumber(url.searchParams.get("year"));
  const limit = parseLimit(url, 100, 1000);

  const conditions = [];
  const binds = [];
  if (user) {
    conditions.push("user_name = ?");
    binds.push(user);
  }
  if (eventType) {
    conditions.push("event_type = ?");
    binds.push(eventType);
  }
  if (month !== null) {
    conditions.push("month = ?");
    binds.push(month);
  }
  if (year !== null) {
    conditions.push("year = ?");
    binds.push(year);
  }
  const whereClause = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  binds.push(limit);

  const { results } = await env.DB.prepare(`
    SELECT *
    FROM events
    ${whereClause}
    ORDER BY created_at DESC
    LIMIT ?
  `).bind(...binds).all();

  return itemsResponse((results || []).map(mapEventRecord), {
    user,
    event_type: eventType,
    month,
    year,
  });
}

async function getApiKeys(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const url = new URL(request.url);
  const user = url.searchParams.get("user");
  const status = url.searchParams.get("status");
  const limit = parseLimit(url, 100, 1000);

  const conditions = [];
  const binds = [];
  if (user) {
    conditions.push("user_name = ?");
    binds.push(user);
  }
  if (status) {
    conditions.push("status = ?");
    binds.push(status);
  }
  const whereClause = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  binds.push(limit);

  const { results } = await env.DB.prepare(`
    SELECT
      api_key_identity,
      user_name,
      redacted_key,
      platform_created_at,
      status,
      first_seen_at,
      last_seen_at,
      deleted_at,
      final_cost,
      final_tokens,
      final_requests
    FROM api_keys
    ${whereClause}
    ORDER BY last_seen_at DESC
    LIMIT ?
  `).bind(...binds).all();

  return itemsResponse(results || [], { user, status });
}

async function getSummary(request, env) {
  const unauthorized = requireAuth(request, env);
  if (unauthorized) {
    return unauthorized;
  }

  const url = new URL(request.url);
  const month = parseOptionalNumber(url.searchParams.get("month"));
  const year = parseOptionalNumber(url.searchParams.get("year"));
  const periodConditions = [];
  const binds = [];

  if (month !== null) {
    periodConditions.push("month = ?");
    binds.push(month);
  }
  if (year !== null) {
    periodConditions.push("year = ?");
    binds.push(year);
  }

  const periodClause = periodConditions.length
    ? `AND ${periodConditions.join(" AND ")}`
    : "";

  const { results } = await env.DB.prepare(`
    SELECT
      m.name,
      m.budget_limit,
      m.warning_threshold,
      m.status,
      u.cost,
      u.tokens,
      u.requests,
      u.recorded_at,
      u.month,
      u.year
    FROM managed_users m
    LEFT JOIN usage_records u
      ON u.id = (
        SELECT id
        FROM usage_records
        WHERE user_name = m.name
        ${periodClause}
        ORDER BY recorded_at DESC
        LIMIT 1
      )
    ORDER BY COALESCE(u.cost, 0) DESC
  `).bind(...binds).all();

  const items = results || [];
  const summary = items.reduce(
    (accumulator, item) => ({
      cost: accumulator.cost + Number(item.cost || 0),
      tokens: accumulator.tokens + Number(item.tokens || 0),
      requests: accumulator.requests + Number(item.requests || 0),
    }),
    { cost: 0, tokens: 0, requests: 0 }
  );
  summary.cost = Number(summary.cost.toFixed(4));

  return Response.json({
    month,
    year,
    summary,
    items,
    total: items.length,
  });
}
