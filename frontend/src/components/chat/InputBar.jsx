import { useState, useRef } from "react";
import { Send } from "lucide-react";

export default function InputBar({ onSendMessage, isStreaming }) {
  const [query, setQuery] = useState("");
  const textareaRef = useRef(null);

  const handleSend = () => {
    const trimmed = query.trim();
    if (!trimmed || isStreaming) return;
    onSendMessage(trimmed);
    setQuery("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e) => {
    setQuery(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = e.target.scrollHeight + "px";
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={query}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder="Ask about config parameters or floor groupings..."
        rows={1}
        style={{ minHeight: "44px", maxHeight: "120px" }}
        className="w-full border border-gray-300 rounded-2xl px-4 py-2.5 pr-14 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm overflow-y-auto"
      />
      <div className="absolute right-3 bottom-2.5 flex items-center gap-2">
        <button
          onClick={handleSend}
          disabled={isStreaming || !query.trim()}
          className={`rounded-xl p-1.5 transition-colors ${
            isStreaming || !query.trim()
              ? "bg-gray-300 text-white cursor-not-allowed"
              : "bg-blue-600 text-white hover:bg-blue-700"
          }`}
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
