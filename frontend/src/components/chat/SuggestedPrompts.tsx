import { Sparkles } from "lucide-react";
import { DEMO_SCENARIOS, type DemoScenario } from "@/lib/demoScenarios";

/**
 * One-click demo scenario chips.
 *
 * Selecting a chip loads a customer/order/reason that deterministically yields
 * the labeled outcome — the fastest path through the Loom walkthrough.
 */
export function SuggestedPrompts({
  onPick,
  disabled,
}: {
  onPick: (scenario: DemoScenario) => void;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <p className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        <Sparkles className="h-3.5 w-3.5" /> Try a scenario
      </p>
      <div className="flex flex-wrap gap-1.5">
        {DEMO_SCENARIOS.map((scenario) => (
          <button
            key={scenario.label}
            disabled={disabled}
            onClick={() => onPick(scenario)}
            className="rounded-full border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground disabled:opacity-50"
          >
            {scenario.label}
          </button>
        ))}
      </div>
    </div>
  );
}
