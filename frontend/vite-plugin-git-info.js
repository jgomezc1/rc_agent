import { execSync } from "node:child_process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const CWD = dirname(fileURLToPath(import.meta.url));
const ENDPOINT = "/__git-info";

function sh(cmd) {
  try {
    return execSync(cmd, { cwd: CWD, stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim();
  } catch {
    // Not a git checkout, or git is not on PATH. The badge hides itself.
    return null;
  }
}

/** Read the git state of the working tree this dev server is serving from. */
export function readGitInfo() {
  const branch = sh("git rev-parse --abbrev-ref HEAD");
  if (branch === null) return { available: false };

  const commit = sh("git rev-parse --short HEAD");
  // Empty output means clean. Note this walks the working tree, so it is the
  // slowest call here — acceptable because it only runs in dev, per request.
  const status = sh("git status --porcelain");

  return {
    available: true,
    branch: branch === "HEAD" ? `detached@${commit}` : branch,
    commit,
    subject: sh("git log -1 --format=%s"),
    committed: sh("git log -1 --format=%cr"),
    dirty: Boolean(status),
    dirtyCount: status ? status.split("\n").length : 0,
  };
}

/**
 * Exposes the current branch/commit to the UI two ways:
 *
 *   - `__GIT_INFO__`, a build-time constant. This is all a production build
 *     can have, and it is the initial value in dev.
 *   - GET /__git-info in dev, recomputed on every request. This is the part
 *     that matters: Vite serves files from disk, so `git checkout other-branch`
 *     changes what the browser shows without restarting anything. A value
 *     baked in at server start would go stale exactly when you need it.
 */
export default function gitInfoPlugin() {
  return {
    name: "rc-agent-git-info",

    config() {
      return { define: { __GIT_INFO__: JSON.stringify(readGitInfo()) } };
    },

    configureServer(server) {
      server.middlewares.use(ENDPOINT, (_req, res) => {
        res.setHeader("Content-Type", "application/json");
        res.setHeader("Cache-Control", "no-store");
        res.end(JSON.stringify(readGitInfo()));
      });
    },
  };
}
