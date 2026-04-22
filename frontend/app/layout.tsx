import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Vol Surface Lab",
  description: "Research-only implied volatility surfaces from EOD option CSV uploads.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        <footer className="disclaimer">
          <strong>Disclaimer:</strong> Vol Surface Lab is for education and quantitative research
          only. Outputs are not investment advice, not a recommendation to buy or sell any
          security, and may be materially wrong. There is no live market data, no broker
          connectivity, and no suitability assessment. Past or modeled volatility is not
          indicative of future results.
        </footer>
      </body>
    </html>
  );
}
