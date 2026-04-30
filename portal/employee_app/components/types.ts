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
  enabled_sidebar_panels?: string[];
  workflow_packs?: string[];
  kernel_baseline?: {
    version?: string;
    required_lanes?: string[];
    certification_required?: boolean;
  };
};

export type MemorySnapshot = Record<string, { key: string; value: Record<string, unknown> }[]>;

export type OperationalMemoryEntry = {
  key: string;
  value: Record<string, unknown>;
  category: string;
};

export type KnowledgeChunk = {
  chunk_index: number;
  content: string;
};

export type KnowledgeDocument = {
  document_id: string;
  title: string;
  metadata: Record<string, unknown>;
  chunk_count: number;
  chunks: KnowledgeChunk[];
  created_at?: string;
};

export type WorkingMemoryTask = {
  task_id: string;
  values: Record<string, unknown>;
};

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
    requester?: string;
    urgency?: string;
  };
};

export type Briefing = {
  id: string;
  title: string;
  whatHappened: string;
  whyItMatters: string;
  recommendedAction: string;
  evidence: string[];
  createdAt: string;
};

export type AlertItem = {
  id: string;
  title: string;
  summary: string;
  severity: "info" | "warning" | "critical";
  createdAt: string;
};

export type ActivityItem = {
  id: string;
  event_type: string;
  description: string;
  occurred_at: string;
  record_id?: string;
  task_id?: string;
  decision?: string;
  category: "decision" | "communication" | "error" | "system";
};

export type ReasoningRecord = {
  record_id: string;
  task_id: string;
  node_id: string;
  decision: string;
  rationale: string;
  confidence: number;
  inputs_considered: Record<string, unknown>;
  alternatives: { option: string; score: number; why_not_chosen: string }[];
  evidence: { source_type: string; reference: string; content_snippet: string }[];
  modules_invoked: string[];
  token_cost: number;
  latency_ms: number;
  created_at: string;
};

export type EmployeeSettings = {
  communication_preferences: {
    preferred_channels: string[];
    briefing_frequency: "daily" | "twice_daily" | "weekly";
    tone: "concise" | "balanced" | "detailed";
    quiet_hours: string;
  };
  approval_rules: {
    required_actions: string[];
    dollar_threshold: number;
    recipient_threshold: number;
  };
  authority_limits: {
    max_autonomous_action_value: number;
    max_recipients: number;
  };
  organizational_map: {
    people: OrgMapPerson[];
  };
  integrations: {
    connected_tools: string[];
  };
  advanced: {
    confidence_threshold: number;
    council_enabled: boolean;
    learning_enabled: boolean;
  };
};

export type OrgMapPerson = {
  name: string;
  role: string;
  email: string;
  communication_preference: string;
  relationship: string;
};

export type MetricsDashboard = {
  kpis: {
    tasks_total: number;
    avg_confidence: number;
    pending_approvals: number;
    avg_duration_seconds: number;
    estimated_minutes_saved?: number;
  };
  tasks_by_day: Array<{ date: string; tasks: number }>;
  approval_mix: Array<{ name: string; value: number }>;
  activity_mix: Array<{ name: string; value: number }>;
  confidence_trend: Array<{ label: string; confidence: number }>;
};
