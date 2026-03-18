import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Custom table wrapper that adds horizontal scroll for wide tables
const components = {
  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-gray-200">
      <table className="min-w-full text-xs border-collapse">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-gray-50 sticky top-0">
      {children}
    </thead>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-semibold text-gray-700 border-b border-gray-200 whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-gray-600 border-b border-gray-100 whitespace-nowrap">
      {children}
    </td>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-gray-50 transition-colors">
      {children}
    </tr>
  ),
};

export default function MessageBubble({ message }) {
  const { role, content, isStreaming } = message;

  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[90%] sm:max-w-[75%] ml-auto rounded-2xl px-4 py-3 text-white bg-blue-600">
          <p className="whitespace-pre-wrap">{content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[95%] sm:max-w-[85%] bg-white shadow-sm border border-gray-100 rounded-2xl px-3 sm:px-5 py-3 sm:py-4">
        {isStreaming && !content ? (
          <div className="flex gap-1 py-2">
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
            <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
              {isStreaming ? content + " \u25CB" : content}
            </ReactMarkdown>
            {isStreaming && (
              <span className="animate-pulse text-gray-400">{"\u258B"}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
