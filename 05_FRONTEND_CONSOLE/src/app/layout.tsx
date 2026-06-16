import './globals.css';
import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import { ThemeProvider } from "@/lib/theme";
import { ModeProvider } from "@/lib/mode";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-heading-loaded",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  variable: "--font-mono-loaded",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Chromatic Harness v2 Console",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${ibmPlexMono.variable}`}>
      <body
        style={{
          margin: 0,
          padding: 0,
          minHeight: "100vh",
          background: "var(--cc-bg, #0a0a0a)",
          color: "var(--cc-text, #e0e0e0)",
          fontFamily: "var(--font-body, 'IBM Plex Sans', system-ui, sans-serif)",
        }}
      >
        <ThemeProvider>
          <ModeProvider>{children}</ModeProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
