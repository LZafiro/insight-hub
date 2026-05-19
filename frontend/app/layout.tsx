import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Insight Hub",
  description: "AI-powered research assistant with verifiable citations",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
