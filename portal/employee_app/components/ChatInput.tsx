"use client";

import { useState } from "react";

type Props = {
  onSend: (content: string) => Promise<void>;
  placeholder?: string;
  footerLabel?: string;
};

export function ChatInput({
  onSend,
  placeholder = "Send work to your employee...",
  footerLabel = "Hosted web slice",
}: Props) {
  const [value, setValue] = useState("");

  return (
    <form
      className="rounded-[28px] border border-ink/10 bg-white/85 p-4 shadow-card"
      onSubmit={async (event) => {
        event.preventDefault();
        const trimmed = value.trim();
        if (!trimmed) return;
        await onSend(trimmed);
        setValue("");
      }}
    >
      <textarea
        className="min-h-[120px] w-full resize-none rounded-2xl border border-ink/10 bg-paper/50 p-4 text-sm outline-none"
        placeholder={placeholder}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <div className="mt-3 flex items-center justify-between">
        <div className="text-xs uppercase tracking-[0.22em] text-ink/45">{footerLabel}</div>
        <button className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white" type="submit">
          Send
        </button>
      </div>
    </form>
  );
}
