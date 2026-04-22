export type EmployeeAppConfig = {
  employeeId: string;
  employeeName: string;
  employeeRole: string;
  enabledSidebarPanels: string[];
  apiBaseUrl: string;
  wsBaseUrl: string;
  apiToken: string;
  deploymentFormat: string;
};

export const employeeAppConfig: EmployeeAppConfig = {
  employeeId: "demo-employee",
  employeeName: "Forge Employee",
  employeeRole: "Autonomous AI Employee",
  enabledSidebarPanels: ["inbox", "activity", "documents", "memory", "settings", "updates", "metrics"],
  apiBaseUrl: "",
  wsBaseUrl: "",
  apiToken: "",
  deploymentFormat: "web",
};

export function resolveApiBaseUrl(): string {
  if (employeeAppConfig.apiBaseUrl) {
    return employeeAppConfig.apiBaseUrl.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return process.env.NEXT_PUBLIC_EMPLOYEE_API_URL?.replace(/\/$/, "") ?? "http://localhost:8001";
}

export function resolveWsBaseUrl(): string {
  if (employeeAppConfig.wsBaseUrl) {
    return employeeAppConfig.wsBaseUrl.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return window.location.origin.replace(/^http/, "ws");
  }
  return process.env.NEXT_PUBLIC_EMPLOYEE_WS_URL?.replace(/\/$/, "") ?? "ws://localhost:8001";
}
