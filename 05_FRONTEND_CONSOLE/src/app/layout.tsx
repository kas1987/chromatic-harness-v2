import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chromatic Harness v2 Console",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "monospace",
          background: "#0a0a0a",
          color: "#e0e0e0",
          margin: 0,
          padding: "16px",
        }}
      >
        {children}
      </body>
    </html>
  );
}
