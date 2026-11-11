import type { Metadata } from "next";
import { Public_Sans } from "next/font/google";
import "./globals.css";

const sans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "SEOPs", template: "%s | SEOPs" },
  description: "Search performance, traffic and advice for your websites",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={sans.variable}>
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:p-3"
        >
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
