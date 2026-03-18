import { Plus, FolderOpen, ChevronDown } from "lucide-react";
import { useState } from "react";
import { AGENT_LABELS } from "../../lib/constants";

export default function Sidebar({
  onNewChat, conversations, activeId, onSelectConversation,
  projects, activeProject, onSelectProject,
  lastRoute, sessionCost,
}) {
  const [projectDropdown, setProjectDropdown] = useState(false);

  return (
    <div className="w-64 h-full flex flex-col text-white" style={{ backgroundColor: "#0f172a" }}>
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-700 flex items-center gap-3">
        <img src="/LogoProDet.png" alt="ProDet" className="h-9 w-auto" />
        <div>
          <div className="text-sm font-semibold leading-tight">ProDet</div>
          <div className="text-sm font-semibold leading-tight text-blue-400">Agent</div>
        </div>
      </div>

      {/* Project selector */}
      <div className="px-3 py-3 border-b border-slate-700">
        <div className="relative">
          <button
            onClick={() => setProjectDropdown(!projectDropdown)}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors text-sm"
          >
            <FolderOpen size={14} className="text-blue-400 flex-shrink-0" />
            <span className="truncate flex-1 text-left">
              {activeProject || "Select project..."}
            </span>
            <ChevronDown size={14} className="text-gray-400 flex-shrink-0" />
          </button>

          {projectDropdown && (
            <div className="absolute left-0 right-0 top-full mt-1 bg-slate-800 border border-slate-600 rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
              <button
                onClick={() => { onSelectProject(null); setProjectDropdown(false); }}
                className="w-full text-left px-3 py-2 text-sm hover:bg-slate-700 text-gray-400 transition-colors"
              >
                (none)
              </button>
              {(projects || []).map((p) => (
                <button
                  key={p}
                  onClick={() => { onSelectProject(p); setProjectDropdown(false); }}
                  className={`w-full text-left px-3 py-2 text-sm hover:bg-slate-700 truncate transition-colors ${
                    p === activeProject ? "bg-slate-700 text-blue-400" : ""
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* New chat + conversations */}
      <div className="flex-1 overflow-y-auto px-3 py-4">
        <button
          onClick={onNewChat}
          className="w-full border border-slate-600 rounded-xl py-2 text-sm hover:bg-slate-700 flex items-center justify-center gap-2 transition-colors"
        >
          <Plus size={16} />
          New conversation
        </button>

        <div className="text-xs text-gray-500 uppercase tracking-wider mt-4 mb-2 px-2">
          Recent
        </div>

        {(!conversations || conversations.length === 0) ? (
          <p className="text-gray-500 text-xs px-2">Your conversations will appear here</p>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              onClick={() => onSelectConversation?.(conv.id)}
              className={`rounded-lg px-3 py-2 text-sm cursor-pointer hover:bg-slate-700 truncate transition-colors ${
                conv.id === activeId ? "bg-slate-700" : ""
              }`}
            >
              {conv.title}
            </div>
          ))
        )}
      </div>

      {/* Session info */}
      <div className="px-4 py-3 border-t border-slate-700 text-xs text-gray-500">
        {lastRoute && (
          <div className="mb-1">
            Last: <span className="text-gray-400">
              {AGENT_LABELS[lastRoute] || lastRoute}
            </span>
          </div>
        )}
        {sessionCost > 0 && (
          <div>Session cost: <span className="text-blue-400">${sessionCost.toFixed(4)}</span></div>
        )}
      </div>
    </div>
  );
}
