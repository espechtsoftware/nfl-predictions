/** Asserts the production base path and output directory the deployment
 * depends on. Deep-route asset resolution relies on absolute
 * `/static/app/` URLs; this pins the config so a silent change fails
 * loudly instead of shipping relative asset paths.
 */

import { describe, expect, it } from "vitest";
import configText from "../../../vite.config.ts?raw";

describe("vite build configuration", () => {
  it("serves all assets from the absolute /static/app/ base", () => {
    expect(configText).toContain('base: "/static/app/"');
  });

  it("emits into the packaged application static tree", () => {
    expect(configText).toContain('outDir: "../src/nfl_dfs/app/static/app"');
  });

  it("keeps deterministic asset names for release diffing", () => {
    expect(configText).toContain('entryFileNames: "assets/app.js"');
  });
});
