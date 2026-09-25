"use client";

import { useEffect, useState } from "react";

// Every request goes to THIS origin. The browser never learns the service's address and never
// holds its credential; the route handler under /api/agent forwards, having discarded whatever
// identity the client tried to assert.
const API = "/api/agent";

// Mirrors the service's seeded local personas. The picker is a DEV convenience: the server
// validates the selection against its own list, so a hand-crafted value cannot invent a persona.
const PERSONAS = ["analyst", "approver", "auditor", "other-tenant"];

// What happened to the human-review hand-off, in the words the user needs. A result that
// escalated but is not queued must say so rather than read as reviewed.
const REVIEW_ROUTING_TEXT: Record<string, string> = {
  routed: "Sent to the review console.",
  failed: "Could not reach the review console; this proposal is not queued for review.",
  off: "Review routing is off in this deployment; this proposal is not queued for review.",
};

function reviewRoutingOf(body: string): string | undefined {
  try {
    const parsed = JSON.parse(body) as { review_routing?: unknown };
    return typeof parsed.review_routing === "string" ? parsed.review_routing : undefined;
  } catch {
    return undefined;
  }
}

// The regimes `Regulator` accepts (domain/models.py). The service refuses any other value with a
// 422 naming the accepted list, so the console offers exactly these and nothing free-typed.
const REGULATORS = [
  { value: "APRA_CPS230", label: "APRA CPS 230 (Australia)" },
  { value: "DORA", label: "DORA (EU)" },
  { value: "UK_OPRES", label: "UK operational resilience (FCA / PRA / BoE)" },
];

interface CardSummary {
  name?: string;
  description?: string;
  skills?: { id: string; name: string }[];
}

export default function Home() {
  const [persona, setPersona] = useState(PERSONAS[0]);
  // Prefilled with the fictional important business service the local profile maps: its asset
  // inventory, outsourcing register and document corpus all answer for this estate.
  const [serviceId, setServiceId] = useState("ibs-retail-payments");
  const [serviceName, setServiceName] = useState("Retail Payments (FICTIONAL)");
  const [scope, setScope] = useState("projects/fictional");
  const [regulator, setRegulator] = useState(REGULATORS[0].value);
  const [documents, setDocuments] = useState("doc-settlement-runbook");
  const [result, setResult] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState<CardSummary | null>(null);

  // The service names itself, so this UI carries no hardcoded product name to go stale.
  useEffect(() => {
    let live = true;
    fetch(API + "/.well-known/agent-card.json", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((body) => {
        if (live) setCard(body as CardSummary | null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFailed(false);
    try {
      // Comma-separated document ids to ingest into the map first (the process and people
      // chains); an empty field sends an empty list, which the service accepts.
      const documentIds = documents
        .split(",")
        .map((id) => id.trim())
        .filter((id) => id.length > 0);
      const response = await fetch(API + "/v1/tolerance", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dev-Persona": persona },
        body: JSON.stringify({
          scope,
          service_id: serviceId,
          service_name: serviceName,
          regulator,
          document_ids: documentIds,
        }),
      });
      const body = await response.text();
      setFailed(!response.ok);
      setResult(body);
    } catch (error) {
      setFailed(true);
      setResult(String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>{card?.name ?? "Agent console"}</h1>
      <p className="sub">
        {card?.description ??
          "Map an important business service and propose its impact tolerances. The values are deterministic, cited, and routed to a human reviewer."}
      </p>

      <form onSubmit={submit}>
        <fieldset>
          <legend>Who you are</legend>
          <label>
            Seeded dev persona (local profile only; the server resolves identity, not this field)
            <select value={persona} onChange={(event) => setPersona(event.target.value)}>
              {PERSONAS.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>

        <fieldset>
          <legend>The business service</legend>
          <label>
            Service id
            <input value={serviceId} onChange={(event) => setServiceId(event.target.value)} />
          </label>
          <label>
            Service name
            <input value={serviceName} onChange={(event) => setServiceName(event.target.value)} />
          </label>
          <label>
            Asset and register scope
            <input value={scope} onChange={(event) => setScope(event.target.value)} />
          </label>
          <label>
            Regulator
            <select value={regulator} onChange={(event) => setRegulator(event.target.value)}>
              {REGULATORS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Document ids to ingest (comma-separated, optional)
            <input value={documents} onChange={(event) => setDocuments(event.target.value)} />
          </label>
          <button type="submit" disabled={busy || !serviceId.trim() || !serviceName.trim()}>
            {busy ? "Working" : "Propose impact tolerances"}
          </button>
        </fieldset>
      </form>

      {result && REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""] ? (
        <p className="sub" data-review-routing={reviewRoutingOf(result)}>
          {REVIEW_ROUTING_TEXT[reviewRoutingOf(result) ?? ""]}
        </p>
      ) : null}
      {result ? <pre className={failed ? "result error" : "result"}>{result}</pre> : null}

      <footer>
        Synthetic, obviously fictional data only. Identity is resolved server-side and the
        client-asserted actor is discarded; see ui/README.md for the embedding contract.
      </footer>
    </main>
  );
}
