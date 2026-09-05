import { useEffect, useState } from "react";
import { GitBranch } from "lucide-react";

// Substituted at build time by vite-plugin-git-info. In dev this is only the
// first paint — the effect below replaces it with a live read.
const BUILD_INFO = __GIT_INFO__;

/**
 * Shows which branch and commit the running app was served from.
 *
 * The asterisk matters as much as the branch name: Vite serves from disk, so
 * uncommitted edits are on screen too. Branch + commit alone would imply you
 * are looking at that commit when you may not be.
 */
export default function BuildBadge() {
  const [info, setInfo] = useState(BUILD_INFO);

  useEffect(() => {
    if (!import.meta.env.DEV) return;

    // Refresh on mount and whenever the tab regains focus, so a `git checkout`
    // done in the terminal shows up as soon as you look back at the browser.
    const refresh = () =>
      fetch("/__git-info", { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => data && setInfo(data))
        .catch(() => {});

    refresh();
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, []);

  if (!info?.available) return null;

  const tooltip = [
    `branch:  ${info.branch}`,
    `commit:  ${info.commit} — ${info.subject}`,
    `date:    ${info.committed}`,
    info.dirty
      ? `${info.dirtyCount} uncommitted file(s): what you see is NOT exactly this commit`
      : "working tree clean",
  ].join("\n");

  return (
    <div
      className="flex items-center gap-1.5 mb-1.5 font-mono text-[11px] leading-none"
      title={tooltip}
    >
      <GitBranch size={11} className="flex-shrink-0 text-gray-600" />
      <span className="truncate text-gray-400">{info.branch}</span>
      <span className="flex-shrink-0 text-gray-600">{info.commit}</span>
      {info.dirty && (
        <span className="flex-shrink-0 text-amber-500" title="uncommitted changes">
          *
        </span>
      )}
    </div>
  );
}
