/** Corpus Research — React table/foundation slice.
 *
 * A foundation slice, not full parity: the legacy page still owns the
 * interactive heatmap, paired chart, scatter, promotion timeline, network
 * controls, and named scenarios until the visualization and route-parity
 * gates. Renders the read-only projection contract with per-section
 * evidence tiers, paginated tables, and honest non-ready states.
 * Provenance renders as sanitized identity metadata — never raw bucket
 * links. Shape/binding validation happens in guards; the browser performs
 * no cryptographic verification and never implies that it did.
 */

import { useState } from "react";
import { Availability, ProjectionPayload, ViewRow } from "../api/types";
import {
  AvailabilityGate,
  EvidenceBadge,
  PartialNotice,
  StaleBadge,
} from "../app/states";
import { GradeReportPreview } from "./GradeReportPreview";

const PAGE_SIZE = 50;

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
        <dt>projection sha256 (server-verified)</dt>
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

/** Distinct evidence_tier values present in the rows, if any. */
function sectionTiers(rows: readonly ViewRow[]): string[] {
  const tiers = new Set<string>();
  for (const row of rows) {
    const tier = row["evidence_tier"];
    if (typeof tier === "string" && tier.length > 0) tiers.add(tier);
  }
  return [...tiers].sort();
}

export function PaginatedTable({
  label,
  columns,
  rows,
  renderRow,
}: {
  label: string;
  columns: readonly string[];
  rows: readonly ViewRow[];
  renderRow?: (row: ViewRow) => readonly string[];
}) {
  const [page, setPage] = useState(0);
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const clamped = Math.min(page, pageCount - 1);
  const start = clamped * PAGE_SIZE;
  const visible = rows.slice(start, start + PAGE_SIZE);
  return (
    <>
      <div className="table-scroll">
        <table>
          <caption className="visually-hidden">{label}</caption>
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
            {visible.map((row, index) => (
              <tr key={start + index}>
                {(renderRow?.(row) ?? columns.map((column) => cell(row[column]))).map(
                  (text, columnIndex) => (
                    <td key={columnIndex}>{text}</td>
                  ),
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > PAGE_SIZE ? (
        <p className="pager" data-testid={`pager-${label}`}>
          <button
            type="button"
            onClick={() => setPage(Math.max(0, clamped - 1))}
            disabled={clamped === 0}
            aria-label={`${label}: previous page`}
          >
            ◀ prev
          </button>{" "}
          showing {start + 1}–{Math.min(start + PAGE_SIZE, rows.length)} of{" "}
          {rows.length.toLocaleString()}{" "}
          <button
            type="button"
            onClick={() => setPage(Math.min(pageCount - 1, clamped + 1))}
            disabled={clamped >= pageCount - 1}
            aria-label={`${label}: next page`}
          >
            next ▶
          </button>
        </p>
      ) : null}
    </>
  );
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
  const tiers = sectionTiers(rows);
  return (
    <section className="view-section" data-testid={`view-${name}`}>
      <h2>
        {VIEW_TITLES[name] ?? name}
        {tiers.map((tier) => (
          <EvidenceBadge key={tier} tier={tier} />
        ))}
      </h2>
      <p className="view-meta" data-testid={`view-meta-${name}`}>
        {rows.length.toLocaleString()} rows
        {receipt === undefined ? null : (
          <>
            {" "}
            · query <code>{shortHash(receipt.cypher_sha256)}</code> · rows hash{" "}
            <code>{shortHash(receipt.rows_sha256)}</code> (server-verified)
          </>
        )}
      </p>
      {rows.length === 0 ? (
        <p className="view-empty" data-testid={`view-empty-${name}`}>
          No rows in this view — shown as empty, not zero.
        </p>
      ) : (
        <PaginatedTable label={name} columns={columns} rows={rows} />
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
      <h1>Corpus Research — foundation slice</h1>
      <AvailabilityGate availability={availability}>
        {(content) => {
          const projection = content.projection;
          const receipts = new Map(
            projection.query_receipt.queries.map((query) => [
              query.name,
              query,
            ]),
          );
          const emptyList =
            content.state === "ready" ? [] : content.emptyViews;
          return (
            <>
              {content.state === "stale" ? (
                <StaleBadge ageSeconds={content.ageSeconds} />
              ) : null}
              {emptyList.length > 0 ? (
                <PartialNotice emptyViews={emptyList} />
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
