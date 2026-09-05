import { useRef, useEffect, useState } from "react";
import { useChat } from "../hooks/useChat";
import { useProjects } from "../hooks/useProjects";
import AppShell from "../components/layout/AppShell";
import ChatThread from "../components/chat/ChatThread";
import InputBar from "../components/chat/InputBar";

export default function ChatPage() {
  const {
    messages,
    isStreaming,
    sendMessage,
    clearMessages,
    conversations,
    currentConversationId,
    setCurrentConversationId,
    lastRoute,
    sessionCost,
  } = useChat();

  const { projects, activeProject, setActiveProject } = useProjects();
  const [selectedAgent, setSelectedAgent] = useState(null); // null = auto-route
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewChat = () => {
    clearMessages();
  };

  const handleSelectConversation = (id) => {
    clearMessages();
    setCurrentConversationId(id);
  };

  return (
    <AppShell
      onNewChat={handleNewChat}
      conversations={conversations}
      activeConversationId={currentConversationId}
      onSelectConversation={handleSelectConversation}
      projects={projects}
      activeProject={activeProject}
      onSelectProject={setActiveProject}
      selectedAgent={selectedAgent}
      onSelectAgent={setSelectedAgent}
      lastRoute={lastRoute}
      sessionCost={sessionCost}
      footer={
        <InputBar
          onSendMessage={(query) => sendMessage(query, activeProject, messages, selectedAgent)}
          isStreaming={isStreaming}
        />
      }
    >
      <div className="max-w-3xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
        <ChatThread
          messages={messages}
          isStreaming={isStreaming}
          onSelectQuery={(text) => sendMessage(text, activeProject, messages, selectedAgent)}
        />
        <div ref={bottomRef} />
      </div>
    </AppShell>
  );
}
