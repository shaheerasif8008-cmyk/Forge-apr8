"use client";

import { GripVertical, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import type { OrgMapPerson } from "./types";

type Props = {
  value: OrgMapPerson[];
  onChange: (next: OrgMapPerson[]) => void;
};

const EMPTY_PERSON: OrgMapPerson = {
  name: "",
  role: "Colleague",
  email: "",
  communication_preference: "email",
  relationship: "colleague",
};

export function OrgMapEditor({ value, onChange }: Props) {
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  function updatePerson(index: number, patch: Partial<OrgMapPerson>) {
    const next = value.map((person, personIndex) => (personIndex === index ? { ...person, ...patch } : person));
    onChange(next);
  }

  function removePerson(index: number) {
    onChange(value.filter((_, personIndex) => personIndex !== index));
  }

  function movePerson(targetIndex: number) {
    if (dragIndex === null || dragIndex === targetIndex) {
      return;
    }
    const next = [...value];
    const [item] = next.splice(dragIndex, 1);
    next.splice(targetIndex, 0, item);
    setDragIndex(null);
    onChange(next);
  }

  return (
    <div className="space-y-3">
      {value.map((person, index) => (
        <div
          key={`${person.email}-${index}`}
          className="rounded-[22px] border border-ink/10 bg-white/80 p-4"
          draggable
          onDragOver={(event) => event.preventDefault()}
          onDragStart={() => setDragIndex(index)}
          onDrop={() => movePerson(index)}
        >
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">
              <GripVertical className="h-4 w-4" />
              Person {index + 1}
            </div>
            <button className="rounded-full p-2 text-terracotta transition hover:bg-terracotta/10" onClick={() => removePerson(index)} type="button">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Input label="Name" value={person.name} onChange={(next) => updatePerson(index, { name: next })} />
            <Input label="Role" value={person.role} onChange={(next) => updatePerson(index, { role: next })} />
            <Input label="Email" value={person.email} onChange={(next) => updatePerson(index, { email: next })} />
            <Select
              label="Channel"
              value={person.communication_preference}
              options={["email", "slack", "teams", "chat"]}
              onChange={(next) => updatePerson(index, { communication_preference: next })}
            />
            <Select
              label="Relationship"
              value={person.relationship}
              options={["supervisor", "colleague", "stakeholder"]}
              onChange={(next) => updatePerson(index, { relationship: next })}
            />
          </div>
        </div>
      ))}

      <button
        className="inline-flex items-center gap-2 rounded-full border border-ink/15 bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-white"
        onClick={() => onChange([...value, EMPTY_PERSON])}
        type="button"
      >
        <Plus className="h-4 w-4" />
        Add Person
      </button>
    </div>
  );
}

function Input({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="space-y-1 text-sm text-ink/70">
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">{label}</span>
      <input
        className="w-full rounded-2xl border border-ink/10 bg-white px-3 py-2 text-ink outline-none transition focus:border-accent"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function Select({
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
      <select
        className="w-full rounded-2xl border border-ink/10 bg-white px-3 py-2 text-ink outline-none transition focus:border-accent"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}
