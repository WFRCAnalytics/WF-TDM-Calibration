// Post-render script: points the GitHub menu at the repository the site is built from.
//
// wfrc-shared.yml adds a GitHub menu to every site's navbar, written with placeholder links:
//   https://github.com/WFRCAnalytics#wfrc-repo              becomes  https://github.com/<owner>/<repo>
//   https://github.com/WFRCAnalytics#wfrc-repo-issues       becomes  https://github.com/<owner>/<repo>/issues/new
//   https://github.com/WFRCAnalytics#wfrc-repo-discussions  becomes  https://github.com/<owner>/<repo>/discussions/new/choose
// and the "Ask a Question" item is removed when the repository does not have Discussions turned on.
//
// The repository is found from GITHUB_REPOSITORY (set in GitHub Actions), otherwise from the git remote
// `origin`. If neither is available, the links stay on the organization page and the question item is
// removed, so nothing is ever wrong, only less specific. `quarto preview` does not run post-render
// scripts, so a preview shows those organization links until the next `quarto render`.
//
// Quarto runs this with its built-in Deno; there is nothing to install. Needs git only for the remote lookup.

const ORG = "https://github.com/WFRCAnalytics";
const files = (Deno.env.get("QUARTO_PROJECT_OUTPUT_FILES") ?? "")
  .split(/\r?\n/)
  .filter((f) => f.endsWith(".html"));

async function gitRemote(): Promise<string> {
  try {
    const out = await new Deno.Command("git", {
      args: ["config", "--get", "remote.origin.url"],
      stdout: "piped",
      stderr: "null",
    }).output();
    return out.success ? new TextDecoder().decode(out.stdout).trim() : "";
  } catch {
    return "";
  }
}

// "owner/repo" from GITHUB_REPOSITORY, or from https://github.com/owner/repo(.git), git@github.com:owner/repo.git
async function findRepo(): Promise<string | undefined> {
  const env = Deno.env.get("GITHUB_REPOSITORY") ?? "";
  if (/^[^/\s]+\/[^/\s]+$/.test(env)) return env;
  const m = (await gitRemote()).match(/github\.com[:/]+([^/\s]+)\/([^/\s]+?)(?:\.git)?\/?$/);
  return m ? `${m[1]}/${m[2]}` : undefined;
}

async function hasDiscussions(repo: string): Promise<boolean> {
  const headers: Record<string, string> = { "User-Agent": "wfrc-brand", Accept: "application/vnd.github+json" };
  const token = Deno.env.get("GITHUB_TOKEN") ?? Deno.env.get("GH_TOKEN");
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const res = await fetch(`https://api.github.com/repos/${repo}`, { headers, signal: AbortSignal.timeout(4000) });
    return res.ok ? (await res.json()).has_discussions === true : false;
  } catch {
    return false; // offline, private without a token, or rate limited: leave the item out
  }
}

const repo = await findRepo();
const url = repo ? `https://github.com/${repo}` : undefined;
const discussions = repo ? await hasDiscussions(repo) : false;
console.log(`github menu: ${url ?? "no repository found, links stay on the organization page"}` +
  (url ? (discussions ? " (Discussions on)" : " (Discussions off or unknown: no question item)") : ""));

const questionItem = /<li>\s*<a[^>]*#wfrc-repo-discussions"[^>]*>[\s\S]*?<\/a>\s*<\/li>/g;

for (const file of files) {
  let html: string;
  try {
    html = await Deno.readTextFile(file);
  } catch {
    continue;
  }
  if (!html.includes("#wfrc-repo")) continue;
  let out = discussions ? html : html.replace(questionItem, "");
  if (url) {
    out = out
      .replaceAll(`${ORG}#wfrc-repo-issues`, `${url}/issues/new`)
      .replaceAll(`${ORG}#wfrc-repo-discussions`, `${url}/discussions/new/choose`)
      .replaceAll(`${ORG}#wfrc-repo`, url);
  } else {
    out = out.replaceAll(/#wfrc-repo(-issues|-discussions)?/g, "");
  }
  if (out !== html) await Deno.writeTextFile(file, out);
}
