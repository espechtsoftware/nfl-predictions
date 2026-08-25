/** Corpus Research — React 19 parity slice.
 *
 * Renders the read-only projection contract: authority banner, exact release
 * identity and staleness, the six required views, and honest non-ready
 * states. Provenance renders as sanitized identity metadata (generation,
 * hash prefixes, byte counts) — never as raw bucket links.
 */

import { Availability, ProjectionPayload, ViewRow } from "../api/types";
import {
  AvailabilityGate,
  EvidenceBadge,
  PartialNotice,
  StaleBadge,
} from "../app/states";
import { GradeReportPreview } from "./GradeReportPreview";

function shortHash(value: string | undefined): string {
  return value === undefined ? "—" : `${value.slice(0, 12)}…`;
}

function AuthorityBanner({ projection }: { projection: ProjectionPayload }) {
  const flags: readonly [string, boolean][] = [
    ["read-only", projection.read_only],
    ["no graph mutation", !projection.graph_mutation],
    ["no automatic promotion", !projection.automatic_promotion],
    ["no config mutation", !projection.application_config_mutation],
    ["no production authority", !projection.production_policy_authority],
  ];
  return (
    <section className="authority-banner" data-testid="authority-banner">
      <strong>Research projection — not a control plane.</strong>{" "}
      {flags.map(([label, holds]) => (
        <span
          key={label}
          className={holds ? "authority-flag" : "authority-flag violated"}
          data-testid="authority-flag"
        >
          {holds ? label : `VIOLATED: ${label}`}
        </span>
      ))}
    </section>
  );
}

function IdentityStrip({
  projection,
  ageSeconds,
}: {
  projection: ProjectionPayload;
  ageSeconds: number;
}) {
  const source = projection.source_projection_receipt;
  return (
    <dl className="identity-strip" data-testid="identity-strip">
      <div>
        <dt>registry</dt>
        <dd data-testid="identity-registry">{projection.registry_id}</dd>
      </div>
      <div>
        <dt>database · namespace</dt>
        <dd>
          {projection.database} · {projection.namespace}
        </dd>
      </div>
      <div>
        <dt>generated</dt>
        <dd data-testid="identity-generated">
          {projection.generated_at_utc} ({Math.round(ageSeconds / 60)} min ago)
        </dd>
      </div>
      <div>
        <dt>projection sha256</dt>
        <dd>
          <code>{shortHash(projection.projection_sha256)}</code>
        </dd>
      </div>
      <div>
        <dt>source release</dt>
        <dd data-testid="identity-source-release">
          generation {source.registry_release.generation} · sha256{" "}
          <code>{shortHash(source.registry_release.sha256)}</code> ·{" "}
          {source.registry_release.bytes.toLocaleString()} bytes
        </dd>
      </div>
      <div>
        <dt>registry contents</dt>
        <dd data-testid="identity-counts">
          {source.registry_node_count.toLocaleString()} nodes ·{" "}
          {source.registry_relationship_count.toLocaleString()} relationships ·{" "}
          {source.winner_imported
            ? `${source.winner_count} governed winners`
            : "winners not imported"}
        </dd>
      </div>
    </dl>
  );
}

const VIEW_TITLES: Readonly<Record<string, string>> = {
  "preset-registry": "Preset registry (fill vs retrieval)",
  "strategy-lineage": "Strategy lineage",
  "paired-heldout-fill-retrieval-comparison":
    "Paired held-out fill/retrieval comparison",
  "active-pointer-promotion-traversal": "Promotion pointer traversal",
  "lineup-player-team-game-traversal": "Lineup → player → team → game",
  "registry-firewall-census": "Registry firewall census",
};

function columnsFor(rows: readonly ViewRow[]): string[] {
  const seen: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (!seen.includes(key)) seen.push(key);
    }
  }
  return seen;
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString();
  return String(value);
}

function ViewSection({
  name,
  rows,
  receipt,
}: {
  name: string;
  rows: readonly ViewRow[];
  receipt?: { cypher_sha256: string; rows_sha256: string; row_count: number };
}) {
  const columns = columnsFor(rows);
  return (
    <section className="view-section" data-testid={`view-${name}`}>
      <h2>{VIEW_TITLES[name] ?? name}</h2>
      <p className="view-meta" data-testid={`view-meta-${name}`}>
        {rows.length.toLocaleString()} rows
        {receipt === undefined ? null : (
          <>
            {" "}
            · query <code>{shortHash(receipt.cypher_sha256)}</code> · rows hash{" "}
            <code>{shortHash(receipt.rows_sha256)}</code>
          </>
        )}
      </p>
      {rows.length === 0 ? (
        <p className="view-empty" data-testid={`view-empty-${name}`}>
          No rows in this view — shown as empty, not zero.
        </p>
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="visually-hidden">{name}</caption>
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column} scope="col">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr key={index}>
                  {columns.map((column) => (
                    <td key={column}>{cell(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function CorpusResearchPage({
  availability,
}: {
  availability: Availability;
}) {
  return (
    <main className="corpus-research" data-testid="corpus-research-page">
      <h1>
        Corpus Research <EvidenceBadge tier="retrospective-simulated" />
      </h1>
      <AvailabilityGate availability={availability}>
        {(content) => {
          const projection = content.projection;
          const receipts = new Map(
            projection.query_receipt.queries.map((query) => [
              query.name,
              query,
            ]),
          );
          return (
            <>
              {content.state === "stale" ? (
                <StaleBadge ageSeconds={content.ageSeconds} />
              ) : null}
              {content.state === "partial" ? (
                <PartialNotice emptyViews={content.emptyViews} />
              ) : null}
              <AuthorityBanner projection={projection} />
              <IdentityStrip
                projection={projection}
                ageSeconds={content.ageSeconds}
              />
              {Object.entries(projection.views).map(([name, rows]) => (
                <ViewSection
                  key={name}
                  name={name}
                  rows={rows}
                  receipt={receipts.get(name)}
                />
              ))}
              <GradeReportPreview />
            </>
          );
        }}
      </AvailabilityGate>
    </main>
  );
}
