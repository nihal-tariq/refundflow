import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ReasoningPanel } from "./ReasoningPanel";

describe("ReasoningPanel", () => {
  it("shows an empty state when there is no reasoning", () => {
    render(<ReasoningPanel items={[]} />);
    expect(screen.getByText("No reasoning yet")).toBeInTheDocument();
  });

  it("renders node labels and thoughts", () => {
    render(
      <ReasoningPanel
        items={[
          {
            node: "policy_validation",
            thought: "Policy validation produced 1 signal(s): WINDOW_EXCEEDED.",
            tool: "policy_validator",
          },
        ]}
      />,
    );
    expect(screen.getByText("Policy Validation")).toBeInTheDocument();
    expect(screen.getByText(/WINDOW_EXCEEDED/)).toBeInTheDocument();
    expect(screen.getByText("policy_validator")).toBeInTheDocument();
  });
});
