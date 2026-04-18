"use client";

import { resolveApiBaseUrl } from "@/app/config";
import { SettingsForm } from "@/components/SettingsForm";

export default function SettingsPage() {
  return <SettingsForm apiBase={resolveApiBaseUrl()} />;
}
