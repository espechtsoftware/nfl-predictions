/** Minimal typed view registry.
 *
 * Phases 1-2 mount a single page; this module isolates navigation so a real
 * router can be adopted at the route-parity phase without rewriting pages
 * (see the Phase 0 decision record). No routing dependency is added before
 * that reviewed step.
 */

export const APP_VIEWS = ["corpus-research"] as const;
export type AppView = (typeof APP_VIEWS)[number];

export const DEFAULT_VIEW: AppView = "corpus-research";

export function isAppView(value: string): value is AppView {
  return (APP_VIEWS as readonly string[]).includes(value);
}
