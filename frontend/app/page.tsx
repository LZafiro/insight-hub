"use client";

import { useState, useRef, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Citation = {
  chunk_id: string;
  document_id: string;
  document_name: string;
  score: number;
  snippet: string;
};

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
};

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState<string>("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function sendMessage() {
    if (!input.trim() || loading) return;
    if (!token) {
      alert("Set a bearer token (top right) first. See README for getting one.");
      return;
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/v1/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userMsg.content }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages((m) => [
        ...m,
        {
          id: data.id,
          role: "assistant",
          content: data.content,
          citations: data.citations,
        },
      ]);
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Error: ${e instanceof Error ? e.message : "unknown"}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={styles.main}>
      <header style={styles.header}>
        <div style={styles.brand}>
          <span style={styles.brandMark}>◆</span>
          <span style={styles.brandName}>Insight Hub</span>
        </div>
        <input
          type="password"
          placeholder="bearer token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          style={styles.tokenInput}
        />
      </header>

      <section style={styles.hero}>
        <h1 style={styles.title}>
          Ask the <em style={styles.italic}>institutional memory</em>.
        </h1>
        <p style={styles.subtitle}>
          Answers grounded in your documents, with citations you can verify.
        </p>
      </section>

      <div ref={scrollRef} style={styles.chatScroll}>
        {messages.length === 0 ? (
          <p style={styles.empty}>No messages yet. Ask a question below.</p>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
        {loading && <div style={styles.thinking}>thinking…</div>}
      </div>

      <form
        style={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          sendMessage();
        }}
      >
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask anything about your documents…"
          rows={2}
          style={styles.textarea}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
        />
        <button type="submit" style={styles.submit} disabled={loading || !input.trim()}>
          Send →
        </button>
      </form>
    </main>
  );
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div style={{ ...styles.bubble, ...(isUser ? styles.bubbleUser : styles.bubbleAssistant) }}>
      <div style={styles.role}>{isUser ? "You" : "Insight Hub"}</div>
      <div style={styles.content}>{message.content}</div>
      {message.citations && message.citations.length > 0 && (
        <div style={styles.citations}>
          <div style={styles.citationsLabel}>Sources</div>
          {message.citations.map((c, idx) => (
            <details key={c.chunk_id} style={styles.citation}>
              <summary style={styles.citationSummary}>
                <span style={styles.citationNum}>[{idx + 1}]</span>
                <span style={styles.citationDoc}>{c.document_name}</span>
                <span style={styles.citationScore}>{(c.score * 100).toFixed(0)}%</span>
              </summary>
              <p style={styles.citationSnippet}>{c.snippet}…</p>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  main: {
    minHeight: "100vh",
    maxWidth: "780px",
    margin: "0 auto",
    padding: "32px 24px",
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    paddingBottom: "16px",
    borderBottom: "1px solid var(--border)",
  },
  brand: { display: "flex", alignItems: "center", gap: "10px" },
  brandMark: { color: "var(--accent)", fontSize: "20px" },
  brandName: { fontFamily: "var(--font-display)", fontSize: "20px", fontWeight: 500 },
  tokenInput: {
    border: "1px solid var(--border)",
    padding: "6px 10px",
    fontSize: "12px",
    fontFamily: "var(--font-mono)",
    background: "var(--bg-elevated)",
    borderRadius: "var(--radius-sm)",
    width: "200px",
  },
  hero: { padding: "20px 0" },
  title: {
    fontFamily: "var(--font-display)",
    fontWeight: 300,
    fontSize: "48px",
    lineHeight: 1.05,
    letterSpacing: "-0.02em",
  },
  italic: { fontStyle: "italic", color: "var(--accent)", fontWeight: 400 },
  subtitle: {
    marginTop: "12px",
    color: "var(--ink-soft)",
    fontSize: "16px",
    maxWidth: "480px",
  },
  chatScroll: {
    flex: 1,
    minHeight: "240px",
    maxHeight: "60vh",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    padding: "8px 0",
  },
  empty: {
    color: "var(--ink-faint)",
    fontStyle: "italic",
    textAlign: "center",
    padding: "40px 0",
  },
  thinking: {
    color: "var(--ink-faint)",
    fontFamily: "var(--font-mono)",
    fontSize: "13px",
    padding: "8px 16px",
  },
  bubble: {
    padding: "14px 18px",
    borderRadius: "var(--radius-md)",
    maxWidth: "85%",
  },
  bubbleUser: {
    alignSelf: "flex-end",
    background: "var(--ink)",
    color: "var(--bg)",
  },
  bubbleAssistant: {
    alignSelf: "flex-start",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    boxShadow: "var(--shadow-sm)",
  },
  role: {
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    marginBottom: "6px",
    opacity: 0.6,
  },
  content: { fontSize: "15px", lineHeight: 1.6, whiteSpace: "pre-wrap" },
  citations: {
    marginTop: "14px",
    paddingTop: "12px",
    borderTop: "1px solid var(--border)",
  },
  citationsLabel: {
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "var(--ink-faint)",
    marginBottom: "8px",
  },
  citation: { marginTop: "4px", fontSize: "13px" },
  citationSummary: {
    cursor: "pointer",
    display: "flex",
    gap: "10px",
    alignItems: "center",
    padding: "4px 0",
  },
  citationNum: {
    fontFamily: "var(--font-mono)",
    color: "var(--accent)",
    fontWeight: 500,
  },
  citationDoc: { flex: 1, color: "var(--ink-soft)" },
  citationScore: {
    fontFamily: "var(--font-mono)",
    fontSize: "11px",
    color: "var(--ink-faint)",
  },
  citationSnippet: {
    marginTop: "6px",
    padding: "10px 12px",
    background: "var(--accent-soft)",
    borderLeft: "2px solid var(--accent)",
    fontSize: "13px",
    color: "var(--ink-soft)",
    fontStyle: "italic",
  },
  form: {
    display: "flex",
    gap: "10px",
    paddingTop: "12px",
    borderTop: "1px solid var(--border)",
  },
  textarea: {
    flex: 1,
    border: "1px solid var(--border)",
    background: "var(--bg-elevated)",
    padding: "12px 14px",
    borderRadius: "var(--radius-md)",
    resize: "none",
    fontSize: "15px",
    outline: "none",
  },
  submit: {
    background: "var(--ink)",
    color: "var(--bg)",
    padding: "0 22px",
    borderRadius: "var(--radius-md)",
    fontFamily: "var(--font-mono)",
    fontSize: "13px",
    letterSpacing: "0.04em",
    alignSelf: "stretch",
  },
};
