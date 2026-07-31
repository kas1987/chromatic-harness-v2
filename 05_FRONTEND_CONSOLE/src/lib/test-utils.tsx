import React, { type ReactElement } from "react";
import { render as rtlRender, type RenderOptions } from "@testing-library/react";
import { ThemeProvider } from "./theme";

function AllTheProviders({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}

export function render(ui: ReactElement, options?: Omit<RenderOptions, "wrapper">) {
  return rtlRender(ui, { wrapper: AllTheProviders, ...options });
}

// Re-export everything else from Testing Library so tests can switch with a single import change.
export * from "@testing-library/react";
