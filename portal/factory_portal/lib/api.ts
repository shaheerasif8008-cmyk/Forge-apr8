"use client";

function stripTrailingSlash(value: string): string {
  return value.replace(/\/$/, "");
}

export type Build = {
  id: string;
  requirements_id?: string | null;
  blueprint_id?: string | null;
  org_id: string;
  status: string;
  iteration: number;
  logs: Array<Record<string, unknown>>;
  artifacts: Array<Record<string, unknown>>;
  test_report: Record<string, unknown>;
  metadata: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
};

export type Deployment = {
  id: string;
  build_id: string;
  org_id: string;
  format: string;
  status: string;
  access_url: string;
  infrastructure: Record<string, unknown>;
  integrations: Array<Record<string, unknown>>;
  health_last_checked?: string | null;
  created_at: string;
  activated_at?: string | null;
};

export function resolveFactoryApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const configured = (window as typeof window & { __FORGE_API_BASE__?: string }).__FORGE_API_BASE__;
    if (configured) {
      return stripTrailingSlash(configured);
    }
  }
  return stripTrailingSlash(process.env.NEXT_PUBLIC_FACTORY_API_URL ?? "http://localhost:8000");
}

async function getJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type AnalystSessionResponse = {
  session_id: string;
  employee_type: string;
  risk_tier: string;
  clarifying_questions: string[];
  transcript: Array<{ role: string; content: string }>;
  next_question: string;
  completeness_score: number;
  is_complete: boolean;
  requirements_id: string;
  timed_out: boolean;
};

export async function startAnalystSession(orgId: string, prompt: string): Promise<AnalystSessionResponse> {
  return getJson<AnalystSessionResponse>(`${resolveFactoryApiBaseUrl()}/api/v1/analyst/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ org_id: orgId, prompt }),
  });
}

export async function sendAnalystMessage(sessionId: string, content: string): Promise<AnalystSessionResponse> {
  return getJson<AnalystSessionResponse>(`${resolveFactoryApiBaseUrl()}/api/v1/analyst/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role: "user", content }),
  });
}

export async function fetchRequirements(sessionId: string): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${resolveFactoryApiBaseUrl()}/api/v1/analyst/sessions/${sessionId}/requirements`, {
    method: "POST",
  });
}

export async function previewBlueprint(requirements: Record<string, unknown>): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${resolveFactoryApiBaseUrl()}/api/v1/analyst/blueprint-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ requirements }),
  });
}

export async function commissionFromSession(sessionId: string, orgId: string): Promise<{ commission_id: string; build_id: string }> {
  return getJson<{ commission_id: string; build_id: string }>(
    `${resolveFactoryApiBaseUrl()}/api/v1/analyst/sessions/${sessionId}/commission?org_id=${encodeURIComponent(orgId)}`,
    { method: "POST" },
  );
}

export async function fetchBuild(buildId: string): Promise<Build> {
  return getJson<Build>(`${resolveFactoryApiBaseUrl()}/api/v1/builds/${buildId}`);
}

export async function retryBuild(buildId: string): Promise<Build> {
  return getJson<Build>(`${resolveFactoryApiBaseUrl()}/api/v1/builds/${buildId}/retry`, { method: "POST" });
}

export async function fetchRoster(orgId: string): Promise<Deployment[]> {
  return getJson<Deployment[]>(`${resolveFactoryApiBaseUrl()}/api/v1/roster?org_id=${encodeURIComponent(orgId)}`);
}

export async function fetchDeployment(deploymentId: string): Promise<Deployment> {
  return getJson<Deployment>(`${resolveFactoryApiBaseUrl()}/api/v1/roster/${deploymentId}`);
}

export async function pauseDeployment(deploymentId: string): Promise<Deployment> {
  return getJson<Deployment>(`${resolveFactoryApiBaseUrl()}/api/v1/roster/${deploymentId}/stop`, { method: "POST" });
}

export async function restartDeployment(deploymentId: string): Promise<Deployment> {
  return getJson<Deployment>(`${resolveFactoryApiBaseUrl()}/api/v1/roster/${deploymentId}/restart`, { method: "POST" });
}

export async function rollbackDeployment(deploymentId: string): Promise<Deployment> {
  return getJson<Deployment>(`${resolveFactoryApiBaseUrl()}/api/v1/roster/${deploymentId}/rollback`, { method: "POST" });
}

export async function fetchMonitoringEvents(deploymentId: string): Promise<Array<Record<string, unknown>>> {
  return getJson<Array<Record<string, unknown>>>(`${resolveFactoryApiBaseUrl()}/api/v1/monitoring/${deploymentId}/events`);
}

export async function fetchMonitoringMetrics(deploymentId: string): Promise<Array<Record<string, unknown>>> {
  return getJson<Array<Record<string, unknown>>>(`${resolveFactoryApiBaseUrl()}/api/v1/monitoring/${deploymentId}/metrics`);
}

export async function fetchUpdates(deploymentId: string): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${resolveFactoryApiBaseUrl()}/api/v1/updates/${deploymentId}`);
}

export async function scheduleModuleUpgrade(
  deploymentId: string,
  payload: { component_id: string; target_version: string; summary: string },
): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${resolveFactoryApiBaseUrl()}/api/v1/updates/${deploymentId}/modules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
