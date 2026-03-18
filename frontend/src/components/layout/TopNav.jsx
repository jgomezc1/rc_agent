import { Menu } from "lucide-react";
import { AGENT_LABELS, AGENT_COLORS } from "../../lib/constants";

export default function TopNav({ activeProject, lastRoute, onMenuClick }) {
  const agentColor = lastRoute ? AGENT_COLORS[lastRoute] : null;
  const agentLabel = lastRoute ? AGENT_LABELS[lastRoute] : null;

  return (
    <div className="h-14 min-h-[56px] flex-shrink-0 border-b border-gray-100 bg-white flex items-center px-4 sm:px-6">
      {/* Hamburger — mobile only */}
      <button
        onClick={onMenuClick}
        className="mr-3 text-gray-500 hover:text-gray-700 transition-colors md:hidden"
      >
        <Menu size={22} />
      </button>

      <div className="flex-1 flex items-center gap-3">
        {activeProject && (
          <span className="text-xs font-medium px-3 py-1 rounded-full bg-blue-100 text-blue-700">
            {activeProject}
          </span>
        )}
        {agentLabel && agentColor && (
          <span className={`text-xs font-medium px-3 py-1 rounded-full ${agentColor.bg} ${agentColor.text}`}>
            {agentLabel}
          </span>
        )}
      </div>
    </div>
  );
}
