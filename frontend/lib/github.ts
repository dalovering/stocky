// GitHub API access for the software-update card. Deliberately outside lib/api.ts — GitHub is
// not our backend: different host, no credentials, and every helper degrades to null when
// offline or rate-limited (the card then falls back to manual instructions).

const REPO = "dalovering/stocky";

export interface GitHubBranchHead {
  sha: string; // short
  date: string | null; // ISO commit date
}

export interface GitHubTag {
  name: string;
  sha: string; // short
}

export async function fetchMainHead(): Promise<GitHubBranchHead | null> {
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/commits/main`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!res.ok) return null;
    const body = await res.json();
    return {
      sha: typeof body.sha === "string" ? body.sha.slice(0, 7) : "",
      date: body.commit?.committer?.date ?? null,
    };
  } catch {
    return null;
  }
}

export async function fetchTags(): Promise<GitHubTag[] | null> {
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/tags?per_page=15`, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { name: string; commit: { sha: string } }[];
    return body.map((t) => ({ name: t.name, sha: t.commit.sha.slice(0, 7) }));
  } catch {
    return null;
  }
}
