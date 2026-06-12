import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecisionBadge } from "./DecisionBadge";

describe("DecisionBadge", () => {
  it("renders the approved label", () => {
    render(<DecisionBadge decision="APPROVED" />);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("renders the denied label", () => {
    render(<DecisionBadge decision="DENIED" />);
    expect(screen.getByText("Denied")).toBeInTheDocument();
  });

  it("renders the escalated label", () => {
    render(<DecisionBadge decision="ESCALATED" />);
    expect(screen.getByText("Escalated")).toBeInTheDocument();
  });
});
