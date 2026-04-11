export type MessageType = "text" | "brief_card" | "approval_request" | "status_update";

export type Brief = {
  brief_id?: string;
  executive_summary?: string;
  confidence_score?: number;
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
