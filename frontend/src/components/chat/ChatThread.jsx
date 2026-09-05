import MessageBubble from "./MessageBubble";
import EmptyState from "./EmptyState";

export default function ChatThread({ messages, isStreaming, onSelectQuery }) {
  if (!messages || messages.length === 0) {
    return <EmptyState onSelectQuery={onSelectQuery} />;
  }

  return (
    <div className="flex flex-col gap-4">
      {(messages || []).map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
    </div>
  );
}
