"use client";

import type {
  ActivityItem,
  AlertItem,
  Approval,
  Briefing,
  EmployeeSettings,
  MemorySnapshot,
  ReasoningRecord,
  UpdateStatus,
} from "@/components/types";

async function getJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchApprovals(apiBase: string): Promise<Approval[]> {
  return getJson<Approval[]>(`${apiBase}/api/v1/approvals`);
}

export async function resolveApproval(
  apiBase: string,
  id: string,
  decision: "approve" | "decline" | "modify",
  note = "",
): Promise<Approval> {
  return getJson<Approval>(`${apiBase}/api/v1/approvals/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision, note }),
  });
}

export async function fetchBriefings(apiBase: string): Promise<Briefing[]> {
  const history = await getJson<{ messages: Array<Record<string, unknown>> }>(
    `${apiBase}/api/v1/chat/history?conversation_id=default`,
  );
  return history.messages
    .filter((message) => {
      const metadata = (message.metadata as Record<string, unknown> | undefined) ?? {};
      return Boolean(metadata.briefing) || String(message.content ?? "").toLowerCase().includes("briefing");
    })
    .map((message, index) => {
      const content = String(message.content ?? "");
      const parts = content.split(". ").filter(Boolean);
      return {
        id: String(message.id ?? `briefing-${index}`),
        title: "Daily Briefing",
        whatHappened: parts[0] ?? content,
        whyItMatters: parts[1] ?? "This update may affect priorities or escalation decisions.",
        recommendedAction: parts[2] ?? "Review the latest actions and follow up where needed.",
        evidence: parts.slice(3),
        createdAt: String(message.created_at ?? new Date().toISOString()),
      };
    });
}

export async function fetchAlerts(apiBase: string): Promise<AlertItem[]> {
  const activity = await fetchActivity(apiBase, 50);
  return activity
    .filter((item) => item.category === "error" || item.description.toLowerCase().includes("failed"))
    .slice(0, 12)
    .map((item) => ({
      id: item.id,
      title: item.event_type.replaceAll("_", " "),
      summary: item.description,
      severity: item.category === "error" ? "critical" : "warning",
      createdAt: item.occurred_at,
    }));
}

export async function fetchActivity(apiBase: string, limit = 50): Promise<ActivityItem[]> {
  const raw = await getJson<Array<Record<string, unknown>>>(`${apiBase}/api/v1/activity?limit=${limit}`);
  return raw.map((item, index) => {
    const eventType = String(item.event_type ?? item.node_id ?? item.node ?? "event");
    const details = (item.details as Record<string, unknown> | undefined) ?? {};
    const description = String(
      item.decision
        ?? details.decision
        ?? details.message
        ?? details.note
        ?? details.node
        ?? eventType.replaceAll("_", " "),
    );
    const lower = eventType.toLowerCase();
    const category: ActivityItem["category"] =
      lower.includes("approval") || lower.includes("decision") || lower.includes("reasoning")
        ? "decision"
        : lower.includes("message") || lower.includes("briefing") || lower.includes("communication")
          ? "communication"
          : lower.includes("error") || lower.includes("failed")
            ? "error"
            : "system";
    return {
      id: String(item.id ?? item.record_id ?? `${eventType}-${index}`),
      event_type: eventType,
      description,
      occurred_at: String(item.occurred_at ?? new Date().toISOString()),
      record_id: item.record_id ? String(item.record_id) : undefined,
      task_id: item.task_id ? String(item.task_id) : undefined,
      decision: item.decision ? String(item.decision) : undefined,
      category,
    };
  });
}

export async function fetchReasoningRecord(apiBase: string, recordId: string): Promise<ReasoningRecord> {
  return getJson<ReasoningRecord>(`${apiBase}/api/v1/reasoning/record/${recordId}`);
}

export async function fetchReasoningRecords(apiBase: string, taskId: string): Promise<ReasoningRecord[]> {
  return getJson<ReasoningRecord[]>(`${apiBase}/api/v1/reasoning/${taskId}`);
}

export async function fetchSettings(apiBase: string): Promise<EmployeeSettings> {
  return getJson<EmployeeSettings>(`${apiBase}/api/v1/settings`);
}

export async function patchSettings(apiBase: string, values: Partial<EmployeeSettings>): Promise<EmployeeSettings> {
  return getJson<EmployeeSettings>(`${apiBase}/api/v1/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ values }),
  });
}

export async function fetchMetrics(apiBase: string): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${apiBase}/api/v1/metrics`);
}

export async function fetchMemory(apiBase: string): Promise<MemorySnapshot> {
  return getJson<MemorySnapshot>(`${apiBase}/api/v1/memory`);
}

export async function fetchUpdates(apiBase: string): Promise<UpdateStatus> {
  return getJson<UpdateStatus>(`${apiBase}/api/v1/updates`);
}
