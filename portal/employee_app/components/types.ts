export type MessageType = "text" | "brief_card" | "approval_request" | "status_update";

export type Brief = {
  title?: string;
  brief_id?: string;
  executive_summary?: string;
  drafted_response?: string;
  confidence_score?: number;
  action_items?: string[];
  schedule_updates?: string[];
  client_info?: {
    client_name?: string;
    client_email?: string;
    client_phone?: string;
    matter_type?: string;
    urgency?: string;
    estimated_value?: string;
    key_facts?: string[];
  };
  analysis?: {
    summary?: string;
    qualification_decision?: string;
    risk_flags?: string[];
    recommended_actions?: string[];
  };
  next_steps?: string[];
  flags?: string[];
};

export type EmployeeMeta = {
  employee_name: string;
  role_title: string;
  workflow: string;
  badge: string;
  capabilities: string[];
  deployment_format: string;
};

export type MemorySnapshot = Record<string, { key: string; value: Record<string, unknown> }[]>;

export type UpdateStatus = {
  security?: Record<string, unknown>;
  learning?: Record<string, unknown>;
  modules?: Record<string, unknown>;
  policies?: Record<string, unknown>;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  message_type: MessageType;
  metadata?: Record<string, unknown>;
};

export type Approval = ChatMessage & {
  metadata?: {
    status?: string;
    task_id?: string;
    brief?: Brief;
    note?: string;
    decision?: string;
  };
};
