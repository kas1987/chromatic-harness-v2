import type { Metadata } from "next";
import { ThemeProvider } from "@/lib/theme";
import { ModeProvider } from "@/lib/mode";

export const metadata: Metadata = {
  title: "Chromatic Harness v2 Console",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "monospace",
          // Driven by the active asset pack via CSS vars (set in ThemeProvider);
          // fallbacks match the Default Neon pack so first paint is correct.
          background: "var(--cc-bg, #0a0a0a)",
          color: "var(--cc-text, #e0e0e0)",
          margin: 0,
          padding: "16px",
          minHeight: "100vh",
        }}
      >
        <ThemeProvider>
          <ModeProvider>{children}</ModeProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
