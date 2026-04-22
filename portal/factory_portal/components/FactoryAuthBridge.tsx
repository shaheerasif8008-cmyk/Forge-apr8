"use client";

import { useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

import { setFactoryAuthTokenResolver } from "@/lib/api";

export function FactoryAuthBridge() {
  const { getToken } = useAuth();

  useEffect(() => {
    setFactoryAuthTokenResolver(async () => (await getToken()) ?? "");
    return () => {
      setFactoryAuthTokenResolver(null);
    };
  }, [getToken]);

  return null;
}
