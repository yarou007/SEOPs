"use client";

import { useState } from "react";
import { InsightCard } from "@/components/insight-card";
import { Markdown } from "@/components/markdown";
import { ApiError, api } from "@/lib/api";
import { STARTER_QUESTIONS, quotaLabel, sortInsights } from "@/lib/insights";
import type {
  AiInsight,
  AiMessage,
  ConversationSummary,
  DateRange,
  InsightStatus,
  UsageInfo,
} from "@/lib/types";

const message = (error: unknown) =>
  error instanceof ApiError
    ? error.message
    : "Something went wrong. Try again.";

export function InsightsPanel({
  slug,
  canManage,
  range,
  initialUsage,
  initialConversations,
  initialInsights,
}: {
  slug: string;
  canManage: boolean;
  range: DateRange;
  initialUsage: UsageInfo | null;
  initialConversations: ConversationSummary[];
  initialInsights: AiInsight[];
}) {
  const [usage, setUsage] = useState<UsageInfo | null>(initialUsage);
  const [conversations, setConversations] =
    useState<ConversationSummary[]>(initialConversations);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [insights, setInsights] = useState<AiInsight[]>(initialInsights);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function refresh() {
    try {
      const [status, list, items] = await Promise.all([
        api.insightsStatus(slug),
        api.conversations(slug),
        api.insights(slug),
      ]);
      setUsage(status);
      setConversations(list);
      setInsights(items);
    } catch (caught) {
      setError(message(caught));
    }
  }

  const blocked = !canManage || busy || !usage?.configured || usage.exhausted;

  async function ask(text: string) {
    const trimmed = text.trim();
    if (!trimmed || blocked) return;
    setBusy(true);
    setError("");
    try {
      const reply = await api.ask(slug, {
        question: trimmed,
        conversation_id: conversationId,
        start: range.start,
        end: range.end,
      });
      setConversationId(reply.conversation_id);
      setMessages((current) => [
        ...current,
        {
          id: `local-${reply.message.id}`,
          role: "user",
          content: trimmed,
          suggested_questions: [],
          model: null,
          created_at: reply.message.created_at,
        },
        reply.message,
      ]);
      setQuestion("");
      await refresh();
    } catch (caught) {
      setError(message(caught));
      void api.insightsStatus(slug).then(setUsage, () => undefined);
    } finally {
      setBusy(false);
    }
  }

  async function openConversation(id: string) {
    setError("");
    try {
      const conversation = await api.conversation(slug, id);
      setConversationId(conversation.id);
      setMessages(conversation.messages);
    } catch (caught) {
      setError(message(caught));
    }
  }

  async function setStatus(id: string, status: InsightStatus) {
    setBusy(true);
    try {
      const updated = await api.updateInsight(slug, id, status);
      setInsights((current) =>
        current.map((item) => (item.id === id ? updated : item)),
      );
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  const last = messages.at(-1);
  const suggestions =
    last?.role === "assistant"
      ? last.suggested_questions
      : messages.length
        ? []
        : STARTER_QUESTIONS;

  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
      <section
        className="panel min-w-0 space-y-4 p-4 sm:p-6"
        aria-label="Ask the AI"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Ask about this website</h2>
          {usage && (
            <span
              className={`badge ${usage.configured && !usage.exhausted ? "badge-good" : "badge-warning"}`}
            >
              {quotaLabel(usage)}
            </span>
          )}
        </div>
        <p className="text-xs text-muted">
          Answers use the stored data for {range.start} – {range.end}. AI can be
          wrong: figures marked “unverified” were not found in the data.
        </p>
        {conversations.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-muted" htmlFor="conversation">
              Conversation
            </label>
            <select
              id="conversation"
              className="min-w-0 max-w-full rounded-md border border-border bg-surface px-2 py-1 text-sm"
              value={conversationId ?? ""}
              onChange={(event) => {
                const id = event.target.value;
                if (id) void openConversation(id);
                else {
                  setConversationId(undefined);
                  setMessages([]);
                }
              }}
            >
              <option value="">New conversation</option>
              {conversations.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.title}
                </option>
              ))}
            </select>
          </div>
        )}
        <ol className="space-y-3" aria-live="polite">
          {messages.map((item) => (
            <li
              key={item.id}
              className={
                item.role === "user"
                  ? "ml-auto max-w-[90%] rounded-md bg-accent-soft px-3 py-2 text-sm [overflow-wrap:anywhere]"
                  : "rounded-md border border-border px-3 py-2 text-sm [overflow-wrap:anywhere]"
              }
            >
              {item.role === "assistant" ? (
                <Markdown>{item.content}</Markdown>
              ) : (
                item.content
              )}
            </li>
          ))}
          {busy && (
            <li className="text-sm text-muted">
              Thinking… free models can take a minute or two.
            </li>
          )}
        </ol>
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted">
              {messages.length ? "Better next questions" : "Start with"}
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((text) => (
                <button
                  key={text}
                  type="button"
                  className="button text-left"
                  disabled={blocked}
                  onClick={() => void ask(text)}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        )}
        {error && (
          <p
            role="alert"
            className="rounded-md bg-bad-soft p-3 text-sm text-bad"
          >
            {error}
          </p>
        )}
        {!canManage && (
          <p className="text-sm text-muted">
            Only the website’s creator or an admin can ask questions. You can
            read the answers and insights.
          </p>
        )}
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(question);
          }}
        >
          <label htmlFor="question" className="sr-only">
            Your question
          </label>
          <textarea
            id="question"
            className="min-h-20 min-w-0 flex-1 rounded-md border border-border bg-surface p-2 text-sm"
            maxLength={2000}
            value={question}
            disabled={blocked}
            placeholder="Why did clicks drop on mobile?"
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button
            type="submit"
            className="button button-primary self-end"
            disabled={blocked || !question.trim()}
          >
            {busy ? "Asking…" : "Ask"}
          </button>
        </form>
      </section>
      <section className="min-w-0 space-y-3" aria-label="Insights">
        <h2 className="text-lg font-semibold">Insights</h2>
        {!insights.length ? (
          <p className="panel p-4 text-sm text-muted">
            No insights yet. Ask a question or generate the weekly AI analysis.
          </p>
        ) : (
          <ul className="space-y-3">
            {sortInsights(insights).map((item) => (
              <InsightCard
                key={item.id}
                insight={item}
                canManage={canManage}
                busy={busy}
                onStatus={(status) => void setStatus(item.id, status)}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
