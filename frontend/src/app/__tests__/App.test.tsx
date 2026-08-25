import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../App";
import { degradedStatusFixture } from "../../fixtures/projection";
import { Availability } from "../../api/types";

describe("App", () => {
  it("shows the loading state, then the fetched availability", async () => {
    let resolve: (value: Availability) => void = () => {};
    const pending = new Promise<Availability>((res) => {
      resolve = res;
    });
    render(<App loadAvailability={() => pending} />);
    expect(screen.getByTestId("state-loading")).toBeInTheDocument();
    resolve({ state: "degraded", status: degradedStatusFixture });
    expect(await screen.findByTestId("state-degraded")).toBeInTheDocument();
    expect(screen.queryByTestId("state-loading")).toBeNull();
  });

  it("keeps the shell header and page mount present in every state", async () => {
    render(
      <App
        loadAvailability={async () => ({
          state: "unauthorized",
          httpStatus: 401,
        })}
      />,
    );
    expect(screen.getByText("Corpus Research Observatory")).toBeInTheDocument();
    expect(await screen.findByTestId("state-unauthorized")).toBeInTheDocument();
    expect(screen.getByTestId("corpus-research-page")).toBeInTheDocument();
  });
});
