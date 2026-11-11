"use client";

import { useState } from "react";
import { InsightCard } from "@/components/insight-card";
import { Markdown } from "@/components/markdown";
import { ApiError, api } from "@/lib/api";
import { Bot, Send, Sparkles } from "lucide-react";
import {
  STARTER_QUESTIONS,
  filterInsights,
  quotaLabel,
  quotaPercent,
  type PriorityFilter,
  type StatusFilter,
} from "@/lib/insights";
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
  const [status, setStatusFilter] = useState<StatusFilter>("open");
  const [priority, setPriority] = useState<PriorityFilter>("all");
  const [limit, setLimit] = useState(5);

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
      // A slow answer may still have been saved: reload history, insights and quota.
      void refresh();
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

  const shown = filterInsights(insights, status, priority);
  return (
    <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
      <section
        className="panel flex min-w-0 flex-col gap-4 p-4 sm:p-6 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto"
        aria-label="Ask the AI"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Sparkles size={18} aria-hidden className="text-brass" />
              Ask about this website
            </h2>
            <p className="mt-1 text-xs text-muted">
              Answers use the stored data for {range.start} to {range.end}. AI
              can be wrong: figures marked “unverified” were not found in the
              data.
            </p>
          </div>
          {usage ? (
            <div className="w-44 text-xs">
              <p
                className={
                  usage.configured && !usage.exhausted
                    ? "text-muted"
                    : "text-warning"
                }
              >
                {quotaLabel(usage)}
              </p>
              <div
                className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-muted"
                role="progressbar"
                aria-label="AI requests used today"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={quotaPercent(usage)}
              >
                <div
                  className={`h-full rounded-full ${quotaPercent(usage) >= 90 ? "bg-bad" : "bg-brass"}`}
                  style={{ width: `${quotaPercent(usage)}%` }}
                />
              </div>
            </div>
          ) : (
            <p className="text-xs text-warning">
              AI status could not be loaded. Reload the page to try again.
            </p>
          )}
        </div>
        {conversations.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs text-muted" htmlFor="conversation">
              Conversation
            </label>
            <select
              id="conversation"
              className="min-w-0 max-w-full text-sm"
              value={conversationId ?? ""}
              disabled={busy}
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
                  ? "ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm text-surface [overflow-wrap:anywhere]"
                  : "flex max-w-[95%] gap-3 [overflow-wrap:anywhere]"
              }
            >
              {item.role === "assistant" ? (
                <>
                  <span className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-full bg-brass-soft text-brass">
                    <Bot size={15} aria-hidden />
                  </span>
                  <div className="min-w-0 rounded-2xl rounded-tl-sm bg-surface-muted px-4 py-3 text-sm">
                    <Markdown>{item.content}</Markdown>
                  </div>
                </>
              ) : (
                item.content
              )}
            </li>
          ))}
          {busy && (
            <li className="flex items-center gap-2 text-sm text-muted">
              <Bot
                size={15}
                aria-hidden
                className="motion-safe:animate-pulse"
              />
              Thinking… free AI models can take a minute or two.
            </li>
          )}
        </ol>
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted">
              {messages.length ? "Good next questions" : "Try one of these"}
            </p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((text) => (
                <button
                  key={text}
                  type="button"
                  className="rounded-full border border-border bg-surface px-3 py-1.5 text-left text-sm hover:border-accent hover:text-accent disabled:opacity-50"
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
            read the answers and advice.
          </p>
        )}
        <form
          className="mt-auto flex items-end gap-2 rounded-xl border border-border bg-surface p-2 focus-within:border-accent"
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
            className="min-h-16 min-w-0 flex-1 resize-y border-0 bg-transparent p-2 text-sm outline-none"
            maxLength={2000}
            value={question}
            disabled={blocked}
            placeholder="Ask anything, for example: why did clicks drop on phones?"
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void ask(question);
              }
            }}
          />
          <button
            type="submit"
            className="button button-primary"
            disabled={blocked || !question.trim()}
          >
            <Send size={15} aria-hidden />
            {busy ? "Asking…" : "Ask"}
          </button>
        </form>
      </section>
      <section className="min-w-0 space-y-3" aria-label="Advice">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Advice</h2>
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="status-filter">
              Show advice
            </label>
            <select
              id="status-filter"
              className="text-xs"
              value={status}
              onChange={(event) =>
                setStatusFilter(event.target.value as StatusFilter)
              }
            >
              <option value="open">Open</option>
              <option value="done">Done</option>
              <option value="dismissed">Dismissed</option>
              <option value="all">All</option>
            </select>
            <label className="sr-only" htmlFor="priority-filter">
              Priority
            </label>
            <select
              id="priority-filter"
              className="text-xs"
              value={priority}
              onChange={(event) =>
                setPriority(event.target.value as PriorityFilter)
              }
            >
              <option value="all">Any priority</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </div>
        </div>
        {!shown.length ? (
          <p className="panel p-4 text-sm text-muted">
            {insights.length
              ? "No advice matches these filters."
              : "No advice yet. Ask a question, or generate the weekly AI analysis on the Overview."}
          </p>
        ) : (
          <ul className="space-y-3">
            {shown.slice(0, limit).map((item) => (
              <InsightCard
                key={item.id}
                insight={item}
                canManage={canManage}
                busy={busy}
                onStatus={(next) => void setStatus(item.id, next)}
              />
            ))}
          </ul>
        )}
        {shown.length > limit && (
          <button
            type="button"
            className="button w-full"
            onClick={() => setLimit((current) => current + 10)}
          >
            Show more advice ({shown.length - limit} more)
          </button>
        )}
      </section>
    </div>
  );
}
