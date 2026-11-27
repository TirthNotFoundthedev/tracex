/* global fetch, console */
const A = "http://localhost:18000";
const post = (p, b, t) =>
  fetch(A + p, {
    method: "POST",
    headers: { "content-type": "application/json", ...(t ? { authorization: "Bearer " + t } : {}) },
    body: JSON.stringify(b),
  });
const get = (p, t) =>
  fetch(A + p, { headers: { authorization: "Bearer " + t } }).then((r) => r.json());
const login = async (u) =>
  (await (await post("/auth/login", { username: u, password: "dev-only-seed-" + u })).json())
    .access_token;
const t = await login("asha");
const cases = await get("/cases?limit=50", t);
const stubs = [];
for (const c of cases.items) {
  const ents = await get(`/cases/${c.case_id}/entities?limit=100`, t);
  for (const e of ents.items ?? []) {
    if (!e.has_hidden_connection) continue;
    const d = await get(`/entities/${e.entity_id}`, t);
    for (const s of d.stubs ?? []) stubs.push(s.stub_id);
  }
}
const long =
  "The same phone number appears in my open case and in a case from another police area. I need to know whether the two cases are about the same group of people before I ask the court for a call record order. Please share the linked records for thirty days so that I can compare the dates and the places in both cases and avoid a second request.";
for (const [i, reason] of [
  [0, long],
  [3, "I need to compare the bank account in both cases."],
]) {
  const r = await post("/access-requests", { stub_id: stubs[i], reason }, t);
  console.log("REQ", r.status, (await r.text()).slice(0, 200));
}
