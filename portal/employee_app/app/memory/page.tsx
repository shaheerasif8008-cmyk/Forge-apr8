"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { resolveApiBaseUrl } from "@/app/config";
import type { KnowledgeDocument, OperationalMemoryEntry, WorkingMemoryTask } from "@/components/types";
import {
  deleteOperationalMemory,
  fetchKnowledgeDocuments,
  fetchOperationalMemory,
  fetchWorkingMemory,
  patchOperationalMemory,
  uploadDocument,
  upsertKnowledgeDocument,
} from "@/lib/api";

type TabId = "operational" | "knowledge" | "working";

export default function MemoryPage() {
  const apiBase = resolveApiBaseUrl();
  const [tab, setTab] = useState<TabId>("operational");
  const [query, setQuery] = useState("");
  const [opsEntries, setOpsEntries] = useState<OperationalMemoryEntry[]>([]);
  const [knowledgeDocuments, setKnowledgeDocuments] = useState<KnowledgeDocument[]>([]);
  const [workingTasks, setWorkingTasks] = useState<WorkingMemoryTask[]>([]);
  const [editingKey, setEditingKey] = useState("");
  const [editingValue, setEditingValue] = useState("{}");
  const [editingCategory, setEditingCategory] = useState("general");
  const [selectedDocumentId, setSelectedDocumentId] = useState("");

  async function loadOperationalMemory(nextQuery = query) {
    const entries = await fetchOperationalMemory(apiBase, { query: nextQuery, limit: 100 });
    setOpsEntries(entries);
  }

  async function loadKnowledgeDocuments() {
    const documents = await fetchKnowledgeDocuments(apiBase);
    setKnowledgeDocuments(documents);
    setSelectedDocumentId((current) => current || documents[0]?.document_id || "");
  }

  async function loadWorkingMemory() {
    setWorkingTasks(await fetchWorkingMemory(apiBase));
  }

  useEffect(() => {
    void loadOperationalMemory();
    void loadKnowledgeDocuments();
    void loadWorkingMemory();
  }, [apiBase]);

  const selectedDocument = knowledgeDocuments.find((document) => document.document_id === selectedDocumentId) ?? null;

  async function saveOperationalEntry() {
    const parsed = JSON.parse(editingValue) as Record<string, unknown>;
    await patchOperationalMemory(apiBase, editingKey, parsed, editingCategory);
    setEditingKey("");
    await loadOperationalMemory();
  }

  async function handleDeleteEntry(key: string) {
    await deleteOperationalMemory(apiBase, key);
    await loadOperationalMemory();
  }

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const document = await uploadDocument(apiBase, { file, metadata: { title: file.name } });
    await loadKnowledgeDocuments();
    setSelectedDocumentId(document.document_id);
    event.target.value = "";
  }

  async function handleReindex() {
    if (!selectedDocument) {
      return;
    }
    await upsertKnowledgeDocument(apiBase, {
      document_id: selectedDocument.document_id,
      title: selectedDocument.title,
      document: selectedDocument.chunks.map((chunk) => chunk.content).join("\n\n"),
      metadata: selectedDocument.metadata,
      replace_existing: true,
    });
    await loadKnowledgeDocuments();
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl px-4 py-6 md:px-8">
      <div className="rounded-[32px] border border-ink/10 bg-white/80 p-6 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Memory Browser</div>
            <h1 className="mt-2 font-display text-4xl text-ink">Inspect, edit, and reindex employee memory.</h1>
          </div>
          <Link className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white" href="/">
            Back to Conversation
          </Link>
        </div>

        <div className="mt-6 inline-flex rounded-full bg-paper p-1">
          {[
            { id: "operational", label: "Operational Memory" },
            { id: "knowledge", label: "Knowledge Base" },
            { id: "working", label: "Working Memory" },
          ].map((item) => (
            <button
              key={item.id}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                tab === item.id ? "bg-white text-ink shadow-sm" : "text-ink/60"
              }`}
              onClick={() => setTab(item.id as TabId)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>

        {tab === "operational" ? (
          <section className="mt-6">
            <div className="flex flex-wrap items-center gap-3">
              <input
                className="min-w-[260px] rounded-full border border-ink/10 bg-paper/60 px-4 py-3 text-sm outline-none"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search keys or values"
                value={query}
              />
              <button
                className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white"
                onClick={() => void loadOperationalMemory(query)}
                type="button"
              >
                Search
              </button>
            </div>

            <div className="mt-5 overflow-hidden rounded-[24px] border border-ink/10">
              <table className="min-w-full divide-y divide-ink/10 text-sm">
                <thead className="bg-paper/70 text-left text-ink/55">
                  <tr>
                    <th className="px-4 py-3">Key</th>
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Value</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink/10 bg-white">
                  {opsEntries.map((entry) => (
                    <tr key={entry.key}>
                      <td className="px-4 py-4 align-top font-medium text-ink">{entry.key}</td>
                      <td className="px-4 py-4 align-top text-ink/70">{entry.category}</td>
                      <td className="px-4 py-4 align-top">
                        {editingKey === entry.key ? (
                          <div className="space-y-2">
                            <input
                              className="w-full rounded-2xl border border-ink/10 px-3 py-2 outline-none"
                              onChange={(event) => setEditingCategory(event.target.value)}
                              value={editingCategory}
                            />
                            <textarea
                              className="min-h-28 w-full rounded-2xl border border-ink/10 px-3 py-2 font-mono text-xs outline-none"
                              onChange={(event) => setEditingValue(event.target.value)}
                              value={editingValue}
                            />
                          </div>
                        ) : (
                          <pre className="whitespace-pre-wrap rounded-2xl bg-paper/55 p-3 text-xs text-ink/75">
                            {JSON.stringify(entry.value, null, 2)}
                          </pre>
                        )}
                      </td>
                      <td className="px-4 py-4 align-top">
                        <div className="flex justify-end gap-2">
                          {editingKey === entry.key ? (
                            <>
                              <button
                                className="rounded-full bg-accent px-3 py-2 text-xs font-semibold text-white"
                                onClick={() => void saveOperationalEntry()}
                                type="button"
                              >
                                Save
                              </button>
                              <button
                                className="rounded-full bg-paper px-3 py-2 text-xs font-semibold text-ink"
                                onClick={() => setEditingKey("")}
                                type="button"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                className="rounded-full bg-ink px-3 py-2 text-xs font-semibold text-white"
                                onClick={() => {
                                  setEditingKey(entry.key);
                                  setEditingCategory(entry.category);
                                  setEditingValue(JSON.stringify(entry.value, null, 2));
                                }}
                                type="button"
                              >
                                Edit
                              </button>
                              <button
                                className="rounded-full bg-terracotta px-3 py-2 text-xs font-semibold text-white"
                                onClick={() => void handleDeleteEntry(entry.key)}
                                type="button"
                              >
                                Delete
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {!opsEntries.length ? (
                    <tr>
                      <td className="px-4 py-8 text-center text-ink/55" colSpan={4}>
                        No operational memory entries found.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        {tab === "knowledge" ? (
          <section className="mt-6 grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
            <div className="rounded-[28px] border border-ink/10 bg-paper/45 p-4">
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">Documents</div>
              <label className="mt-4 flex cursor-pointer items-center justify-center rounded-[22px] border border-dashed border-ink/20 bg-white/80 px-4 py-8 text-center text-sm text-ink/70">
                <input className="hidden" onChange={handleUpload} type="file" />
                Upload a document
              </label>
              <div className="mt-4 space-y-3">
                {knowledgeDocuments.map((document) => (
                  <button
                    key={document.document_id}
                    className={`w-full rounded-[22px] px-4 py-3 text-left transition ${
                      selectedDocumentId === document.document_id ? "bg-ink text-white" : "bg-white/80 text-ink"
                    }`}
                    onClick={() => setSelectedDocumentId(document.document_id)}
                    type="button"
                  >
                    <div className="font-semibold">{document.title}</div>
                    <div className={`mt-1 text-xs ${selectedDocumentId === document.document_id ? "text-white/70" : "text-ink/55"}`}>
                      {document.chunk_count} chunks
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-[28px] border border-ink/10 bg-white/80 p-5 shadow-card">
              {selectedDocument ? (
                <>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">Chunk Detail</div>
                      <h2 className="mt-2 font-display text-3xl text-ink">{selectedDocument.title}</h2>
                    </div>
                    <button
                      className="rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white"
                      onClick={() => void handleReindex()}
                      type="button"
                    >
                      Reindex Document
                    </button>
                  </div>
                  <div className="mt-4 rounded-[22px] bg-paper/45 p-4 text-sm text-ink/70">
                    Metadata: {JSON.stringify(selectedDocument.metadata)}
                  </div>
                  <div className="mt-5 space-y-4">
                    {selectedDocument.chunks.map((chunk) => (
                      <article key={chunk.chunk_index} className="rounded-[22px] border border-ink/10 bg-paper/35 p-4">
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/45">
                          Chunk {chunk.chunk_index + 1}
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink/75">{chunk.content}</p>
                      </article>
                    ))}
                  </div>
                </>
              ) : (
                <div className="rounded-[24px] bg-paper/40 p-8 text-center text-ink/60">
                  No knowledge-base documents uploaded yet.
                </div>
              )}
            </div>
          </section>
        ) : null}

        {tab === "working" ? (
          <section className="mt-6 grid gap-4 md:grid-cols-2">
            {workingTasks.map((task) => (
              <article key={task.task_id} className="rounded-[28px] border border-ink/10 bg-white/80 p-5 shadow-card">
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-ink/45">Task</div>
                <div className="mt-2 break-all font-semibold text-ink">{task.task_id}</div>
                <pre className="mt-4 overflow-x-auto rounded-[22px] bg-paper/45 p-4 text-xs text-ink/75">
                  {JSON.stringify(task.values, null, 2)}
                </pre>
              </article>
            ))}
            {!workingTasks.length ? (
              <div className="rounded-[24px] bg-paper/40 p-8 text-center text-ink/60">
                No working-memory task state is currently cached.
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </main>
  );
}
