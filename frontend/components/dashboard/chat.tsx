"use client";

import { useEffect, useRef, useState } from "react";
import { Badge, Button, Card } from "@/components/ui/primitives";
import { IconArrowRight, IconCheck, IconSparkle } from "@/components/icons";
import { api } from "@/lib/api";
import type { ChatMessage, Project } from "@/lib/types";
import { cn, formatClock } from "@/lib/utils";

const SUGGESTIONS = [
  "Predict the target and build the full pipeline",
  "My dataset is very imbalanced",
  "Find data leakage",
  "My model is overfitting",
  "I want better recall",
  "Explain this prediction to a CEO",
  "Deploy this to Docker",
  "Build a dashboard",
];

export function ChatPanel({
  project,
  onRunStarted,
}: {
  project: Project;
  onRunStarted: (runId: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .getChat(project.id)
      .then((result) => setMessages(result.messages))
      .catch(() => undefined);
  }, [project.id]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, busy]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setDraft("");
    setBusy(true);

    const optimistic: ChatMessage = {
      id: `local-${Date.now()}`,
      project_id: project.id,
      role: "user",
      content: trimmed,
      meta: {},
      created_at: new Date().toISOString(),
    };
    setMessages((current) => [...current, optimistic]);

    try {
      const result = await api.postChat(project.id, trimmed, true);
      setMessages((current) => [...current, result.message]);
      const runId = result.executed?.run_id;
      if (typeof runId === "string") onRunStarted(runId);
    } catch (exception) {
      setMessages((current) => [
        ...current,
        {
          id: `error-${Date.now()}`,
          project_id: project.id,
          role: "assistant",
          content: `I could not reach the backend: ${(exception as Error).message}`,
          meta: {},
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="flex h-[calc(100vh-260px)] min-h-[520px] flex-col overflow-hidden">
      <div className="flex items-center gap-2.5 border-b px-5 py-3.5">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-gradient">
          <IconSparkle className="h-3.5 w-3.5 text-white" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold leading-tight">dataid Assistant</p>
          <p className="truncate text-[11px] text-muted">
            {project.dataset_name ?? "no dataset uploaded"}
          </p>
        </div>
        <Badge tone={project.dataset_path ? "good" : "neutral"}>
          {project.dataset_path ? "Ready" : "Awaiting data"}
        </Badge>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto p-5">
        {messages.length === 0 && (
          <div className="py-6">
            <p className="text-[14px] font-medium">How can I help?</p>
            <p className="mt-1.5 text-[13px] text-secondary">
              Describe the outcome you want. The right agents pick it up — there are no buttons to
              hunt for.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => send(suggestion)}
                  className="rounded-full border px-3 py-1.5 text-[12.5px] text-secondary transition-colors hover:border-brand-500/45 hover:bg-brand-500/[0.06]"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {busy && (
          <div className="flex gap-3">
            <Avatar />
            <div className="flex items-center gap-1.5 rounded-2xl bg-black/[0.04] px-4 py-3.5 dark:bg-white/[0.06]">
              {[0, 1, 2].map((dot) => (
                <span
                  key={dot}
                  className="h-1.5 w-1.5 animate-pulse rounded-full bg-[color:var(--ink-muted)]"
                  style={{ animationDelay: `${dot * 0.16}s` }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
        className="border-t p-4"
      >
        <div className="flex items-end gap-2 rounded-xl border px-3 py-2 focus-within:border-brand-500/50">
          <textarea
            rows={1}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send(draft);
              }
            }}
            placeholder="Ask anything…"
            className="max-h-32 flex-1 resize-none bg-transparent py-1.5 text-[13.5px] outline-none placeholder:text-[color:var(--ink-muted)]"
          />
          <Button type="submit" size="sm" disabled={!draft.trim() || busy} aria-label="Send">
            <IconArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
        <p className="mt-2 px-1 text-[11px] text-muted">
          Enter to send · Shift+Enter for a new line
        </p>
      </form>
    </Card>
  );
}

function Avatar() {
  return (
    <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-gradient">
      <IconSparkle className="h-3.5 w-3.5 text-white" />
    </span>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const meta = message.meta as {
    label?: string;
    agents?: string[];
    steps?: string[];
    detail?: string;
    executed?: { type?: string; run_id?: string } | null;
  };
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "justify-end")}>
      {!isUser && <Avatar />}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed",
          isUser
            ? "bg-brand-gradient text-white"
            : "bg-black/[0.04] text-secondary dark:bg-white/[0.06]",
        )}
      >
        <p>{message.content}</p>

        {!isUser && meta.detail && meta.detail !== message.content && (
          <p className="mt-2.5 text-[12.5px] opacity-80">{meta.detail}</p>
        )}

        {!isUser && meta.steps && meta.steps.length > 0 && (
          <ul className="mt-3.5 space-y-1.5">
            {meta.steps.map((step) => (
              <li key={step} className="flex items-start gap-2 text-[12.5px]">
                <IconCheck
                  className="mt-0.5 h-3.5 w-3.5 shrink-0"
                  style={{ color: "var(--status-good)" }}
                />
                {step}
              </li>
            ))}
          </ul>
        )}

        {!isUser && meta.agents && meta.agents.length > 0 && (
          <div className="mt-3.5 flex flex-wrap gap-1.5">
            {meta.agents.map((agent) => (
              <span
                key={agent}
                className="rounded-md border px-1.5 py-0.5 font-mono text-[10.5px] opacity-75"
              >
                {agent}
              </span>
            ))}
          </div>
        )}

        {!isUser && meta.executed?.run_id && (
          <p className="mt-3 border-t pt-3 text-[12px] opacity-80">
            Started run <span className="font-mono">{meta.executed.run_id}</span> — follow it on the
            Timeline tab.
          </p>
        )}

        <p className={cn("mt-2 text-[10.5px]", isUser ? "text-white/65" : "text-muted")}>
          {formatClock(message.created_at)}
        </p>
      </div>
    </div>
  );
}
