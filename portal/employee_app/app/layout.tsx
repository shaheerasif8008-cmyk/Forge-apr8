import "./globals.css";
import type { Metadata } from "next";

import { employeeAppConfig } from "./config";

export const metadata: Metadata = {
  title: `${employeeAppConfig.employeeName} | Forge Employee`,
  description: employeeAppConfig.employeeRole,
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
