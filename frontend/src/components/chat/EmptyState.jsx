import { Settings, Layers, FileText, Clock, Play, BarChart3 } from "lucide-react";
import { EXAMPLE_QUERIES, AGENT_LABELS, AGENT_COLORS } from "../../lib/constants";

const ICON_MAP = {
  Settings,
  Layers,
  FileText,
  Clock,
  Play,
  BarChart3,
};

export default function EmptyState({ onSelectQuery }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4">
      <img src="/LogoProDet.png" alt="ProDet" className="h-16 w-auto mb-4" />
      <h2 className="text-2xl font-semibold text-gray-700 mb-2">
        ProDet Agent
      </h2>
      <p className="text-gray-400 mb-8 text-center max-w-md">
        Construction Intelligence Platform — configure, optimize, procure, schedule, and run ProDet
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
        {EXAMPLE_QUERIES.map((q, i) => {
          const Icon = ICON_MAP[q.icon];
          const color = AGENT_COLORS[q.agent];
          return (
            <button
              key={i}
              onClick={() => onSelectQuery(q.text)}
              className="bg-white border border-gray-200 rounded-xl p-4 hover:border-blue-300 hover:bg-blue-50 cursor-pointer shadow-sm text-left flex items-start gap-3 transition-colors"
            >
              {Icon && <Icon size={20} className="text-gray-400 mt-0.5 flex-shrink-0" />}
              <div>
                <span className="text-sm text-gray-700">{q.text}</span>
                <span className={`block text-xs mt-1 ${color.text}`}>
                  {AGENT_LABELS[q.agent]}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
