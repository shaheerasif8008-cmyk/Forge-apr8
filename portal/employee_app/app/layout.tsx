import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Forge Employee App",
  description: "Arthur, the legal intake associate",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
