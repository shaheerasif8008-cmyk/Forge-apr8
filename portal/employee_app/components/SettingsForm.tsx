"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, CheckCircle2, Save } from "lucide-react";
import { z } from "zod";

import { fetchSettings, patchSettings } from "@/lib/api";

import { OrgMapEditor } from "./OrgMapEditor";
import type { EmployeeSettings, OrgMapPerson } from "./types";

const settingsSchema = z.object({
  communication_preferences: z.object({
    preferred_channels: z.array(z.string()).min(1),
    briefing_frequency: z.enum(["daily", "twice_daily", "weekly"]),
    tone: z.enum(["concise", "balanced", "detailed"]),
    quiet_hours: z.string().min(1),
  }),
  approval_rules: z.object({
    required_actions: z.array(z.string()),
    dollar_threshold: z.number().min(0),
    recipient_threshold: z.number().min(0),
  }),
  authority_limits: z.object({
    max_autonomous_action_value: z.number().min(0),
    max_recipients: z.number().min(1),
  }),
  organizational_map: z.object({
    people: z.array(
      z.object({
        name: z.string().min(1, "Name is required"),
        role: z.string().min(1, "Role is required"),
        email: z.string().email("Valid email required"),
        communication_preference: z.string().min(1),
        relationship: z.string().min(1),
      }),
    ),
  }),
  integrations: z.object({
    connected_tools: z.array(z.string()),
  }),
  advanced: z.object({
    confidence_threshold: z.number().min(0).max(1),
    council_enabled: z.boolean(),
    learning_enabled: z.boolean(),
  }),
});

type SettingsFormValues = z.infer<typeof settingsSchema>;

type Props = {
  apiBase: string;
};

export function SettingsForm({ apiBase }: Props) {
  const [loadError, setLoadError] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [lastSaved, setLastSaved] = useState<SettingsFormValues | null>(null);
  const form = useForm<SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      communication_preferences: {
        preferred_channels: ["email", "messaging"],
        briefing_frequency: "daily",
        tone: "balanced",
        quiet_hours: "after_5pm",
      },
      approval_rules: {
        required_actions: ["external_send", "contract_approval"],
        dollar_threshold: 1000,
        recipient_threshold: 5,
      },
      authority_limits: {
        max_autonomous_action_value: 1000,
        max_recipients: 5,
      },
      organizational_map: { people: [] },
      integrations: { connected_tools: [] },
      advanced: {
        confidence_threshold: 0.72,
        council_enabled: true,
        learning_enabled: true,
      },
    },
  });

  useEffect(() => {
    const load = async () => {
      try {
        const settings = await fetchSettings(apiBase);
        form.reset(settings);
        setLastSaved(settings);
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : "Unable to load settings");
      }
    };
    void load();
  }, [apiBase, form]);

  async function onSubmit(values: SettingsFormValues) {
    setSaveState("saving");
    const previous = lastSaved;
    setLastSaved(values);
    try {
      const saved = await patchSettings(apiBase, values);
      form.reset(saved);
      setLastSaved(saved);
      setSaveState("saved");
    } catch (error) {
      if (previous) {
        form.reset(previous);
        setLastSaved(previous);
      }
      setLoadError(error instanceof Error ? error.message : "Unable to save settings");
      setSaveState("error");
    }
  }

  const values = form.watch();

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 md:px-8">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link className="inline-flex items-center gap-2 text-sm font-semibold text-ink/60 transition hover:text-ink" href="/">
            <ArrowLeft className="h-4 w-4" />
            Back to employee app
          </Link>
          <h1 className="mt-3 font-display text-5xl text-ink">Settings</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink/65">
            Tune how your employee communicates, escalates, and operates. Changes are validated locally and saved to the runtime configuration.
          </p>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-accent/90"
          onClick={form.handleSubmit(onSubmit)}
          type="button"
        >
          {saveState === "saved" ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          {saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved" : "Save Changes"}
        </button>
      </div>

      {loadError ? <div className="mb-4 rounded-2xl border border-terracotta/25 bg-terracotta/10 p-4 text-sm text-terracotta">{loadError}</div> : null}

      <div className="space-y-4">
        <AccordionSection title="Communication Preferences">
          <div className="grid gap-4 md:grid-cols-2">
            <MultiCheckbox
              label="Preferred Channels"
              options={["email", "messaging", "calendar"]}
              value={values.communication_preferences.preferred_channels}
              onChange={(next) => form.setValue("communication_preferences.preferred_channels", next, { shouldValidate: true })}
            />
            <SelectField
              label="Briefing Frequency"
              value={values.communication_preferences.briefing_frequency}
              options={["daily", "twice_daily", "weekly"]}
              onChange={(next) => form.setValue("communication_preferences.briefing_frequency", next as SettingsFormValues["communication_preferences"]["briefing_frequency"])}
            />
            <SelectField
              label="Tone"
              value={values.communication_preferences.tone}
              options={["concise", "balanced", "detailed"]}
              onChange={(next) => form.setValue("communication_preferences.tone", next as SettingsFormValues["communication_preferences"]["tone"])}
            />
            <SelectField
              label="Quiet Hours"
              value={values.communication_preferences.quiet_hours}
              options={["after_5pm", "after_6pm", "after_7pm"]}
              onChange={(next) => form.setValue("communication_preferences.quiet_hours", next)}
            />
          </div>
        </AccordionSection>

        <AccordionSection title="Approval Rules">
          <div className="grid gap-4 md:grid-cols-2">
            <MultiCheckbox
              label="Actions Requiring Approval"
              options={["external_send", "contract_approval", "calendar_booking", "bulk_outreach"]}
              value={values.approval_rules.required_actions}
              onChange={(next) => form.setValue("approval_rules.required_actions", next)}
            />
            <NumberField
              label="Dollar Threshold"
              value={values.approval_rules.dollar_threshold}
              onChange={(next) => form.setValue("approval_rules.dollar_threshold", next)}
            />
            <NumberField
              label="Recipient Threshold"
              value={values.approval_rules.recipient_threshold}
              onChange={(next) => form.setValue("approval_rules.recipient_threshold", next)}
            />
          </div>
        </AccordionSection>

        <AccordionSection title="Authority Limits">
          <div className="grid gap-4 md:grid-cols-2">
            <RangeField
              label="Confidence Threshold"
              value={values.advanced.confidence_threshold}
              min={0.4}
              max={0.95}
              step={0.01}
              onChange={(next) => form.setValue("advanced.confidence_threshold", next)}
            />
            <NumberField
              label="Max Autonomous Action Value"
              value={values.authority_limits.max_autonomous_action_value}
              onChange={(next) => form.setValue("authority_limits.max_autonomous_action_value", next)}
            />
            <NumberField
              label="Max Recipients"
              value={values.authority_limits.max_recipients}
              onChange={(next) => form.setValue("authority_limits.max_recipients", next)}
            />
          </div>
        </AccordionSection>

        <AccordionSection title="Organizational Map">
          <OrgMapEditor
            onChange={(next: OrgMapPerson[]) => form.setValue("organizational_map.people", next, { shouldValidate: true })}
            value={values.organizational_map.people}
          />
        </AccordionSection>

        <AccordionSection title="Integrations">
          <div className="grid gap-3 md:grid-cols-2">
            {values.integrations.connected_tools.length ? values.integrations.connected_tools.map((tool) => (
              <div key={tool} className="flex items-center justify-between rounded-2xl border border-ink/10 bg-white/85 px-4 py-3">
                <div>
                  <div className="font-semibold text-ink">{tool}</div>
                  <div className="text-xs text-ink/50">Connected and available to the employee runtime.</div>
                </div>
                <button
                  className="rounded-full border border-ink/15 px-3 py-1.5 text-xs font-semibold text-ink/60 transition hover:bg-paper"
                  onClick={() => form.setValue("integrations.connected_tools", values.integrations.connected_tools.filter((entry) => entry !== tool))}
                  type="button"
                >
                  Disconnect
                </button>
              </div>
            )) : <div className="rounded-2xl bg-paper/50 p-4 text-sm text-ink/60">No integrations connected.</div>}
          </div>
        </AccordionSection>

        <AccordionSection title="Advanced">
          <div className="grid gap-4 md:grid-cols-2">
            <ToggleField
              label="Deliberation Council Enabled"
              checked={values.advanced.council_enabled}
              onChange={(checked) => form.setValue("advanced.council_enabled", checked)}
            />
            <ToggleField
              label="Continuous Learning Enabled"
              checked={values.advanced.learning_enabled}
              onChange={(checked) => form.setValue("advanced.learning_enabled", checked)}
            />
          </div>
        </AccordionSection>
      </div>
    </div>
  );
}

function AccordionSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <details className="rounded-[28px] border border-ink/10 bg-white/80 p-5 shadow-card" open>
      <summary className="cursor-pointer list-none text-lg font-semibold text-ink">{title}</summary>
      <div className="mt-5">{children}</div>
    </details>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1 text-sm text-ink/70">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</span>
      <select className="w-full rounded-2xl border border-ink/10 bg-white px-3 py-3" onChange={(event) => onChange(event.target.value)} value={value}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="space-y-1 text-sm text-ink/70">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</span>
      <input
        className="w-full rounded-2xl border border-ink/10 bg-white px-3 py-3"
        min={0}
        onChange={(event) => onChange(Number(event.target.value))}
        type="number"
        value={value}
      />
    </label>
  );
}

function RangeField({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="space-y-2 text-sm text-ink/70">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</span>
      <input className="w-full" max={max} min={min} onChange={(event) => onChange(Number(event.target.value))} step={step} type="range" value={value} />
      <div className="text-sm font-semibold text-ink">{Math.round(value * 100)}%</div>
    </label>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between rounded-2xl border border-ink/10 bg-white/85 px-4 py-3 text-sm text-ink/80">
      <span className="font-medium">{label}</span>
      <button
        aria-pressed={checked}
        className={`h-8 w-14 rounded-full p-1 transition ${checked ? "bg-moss" : "bg-paper"}`}
        onClick={() => onChange(!checked)}
        type="button"
      >
        <span className={`block h-6 w-6 rounded-full bg-white transition ${checked ? "translate-x-6" : "translate-x-0"}`} />
      </button>
    </label>
  );
}

function MultiCheckbox({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string[];
  onChange: (value: string[]) => void;
}) {
  return (
    <fieldset className="space-y-2 rounded-2xl border border-ink/10 bg-white/85 p-4">
      <legend className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</legend>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = value.includes(option);
          return (
            <button
              key={option}
              className={`rounded-full px-3 py-2 text-sm font-semibold transition ${
                active ? "bg-accent text-white" : "bg-paper text-ink/65"
              }`}
              onClick={() => onChange(active ? value.filter((entry) => entry !== option) : [...value, option])}
              type="button"
            >
              {option.replaceAll("_", " ")}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
