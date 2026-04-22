import "./globals.css";
import type { ReactNode } from "react";
import { ClerkProvider } from "@clerk/nextjs";

import { FactoryAuthBridge } from "@/components/FactoryAuthBridge";

export default function RootLayout({ children }: { children: ReactNode }) {
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return (
      <html lang="en">
        <body>{children}</body>
      </html>
    );
  }

  return (
    <html lang="en">
      <body>
        <ClerkProvider>
          <FactoryAuthBridge />
          {children}
        </ClerkProvider>
      </body>
    </html>
  );
}
