import { useState, useCallback } from "react";
import { API_BASE_URL } from "../lib/constants";

export function useChat() {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [lastRoute, setLastRoute] = useState(null);
  const [sessionCost, setSessionCost] = useState(0);

  const sendMessage = useCallback(async (query, project, previousMessages) => {
    const userMsg = { role: "user", content: query, id: Date.now() };
    const assistantId = Date.now() + 1;
    const assistantMsg = {
      role: "assistant",
      content: "",
      id: assistantId,
      isStreaming: true,
    };

    setMessages((prev) => {
      if (prev.length === 0) {
        const convId = Date.now();
        setConversations((c) => [
          { id: convId, title: query.slice(0, 40), date: "Hoy" },
          ...c,
        ]);
        setCurrentConversationId(convId);
      }
      return [...prev, userMsg, assistantMsg];
    });
    setIsStreaming(true);

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          project: project || null,
          chat_history: (previousMessages || [])
            .filter((m) => m.role === "user" || m.role === "assistant")
            .map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6);
          if (!jsonStr) continue;

          try {
            const data = JSON.parse(jsonStr);

            if (data.token) {
              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };
                last.content += data.token;
                updated[updated.length - 1] = last;
                return updated;
              });
            }

            if (data.done) {
              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };
                last.isStreaming = false;
                updated[updated.length - 1] = last;
                return updated;
              });
              setIsStreaming(false);
              if (data.routed_to) setLastRoute(data.routed_to);
              if (data.session_cost) setSessionCost(data.session_cost);
            }

            if (data.error) {
              setMessages((prev) => {
                const updated = [...prev];
                const last = { ...updated[updated.length - 1] };
                last.content = "Error: " + data.error;
                last.isStreaming = false;
                updated[updated.length - 1] = last;
                return updated;
              });
              setIsStreaming(false);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const updated = [...prev];
        const last = { ...updated[updated.length - 1] };
        last.content = "Connection error: " + err.message;
        last.isStreaming = false;
        updated[updated.length - 1] = last;
        return updated;
      });
      setIsStreaming(false);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setCurrentConversationId(null);
    setLastRoute(null);
  }, []);

  return {
    messages,
    isStreaming,
    sendMessage,
    clearMessages,
    conversations,
    currentConversationId,
    setCurrentConversationId,
    lastRoute,
    sessionCost,
  };
}
