import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "SEOPs", template: "%s · SEOPs" },
  description: "SEO performance and weekly review",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
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
