// Mirrors the server's GitHub URL rules so users get instant feedback;
// the server re-validates every request.
const OWNER = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/;
const NAME = /^[A-Za-z0-9_.-]{1,100}$/;

export type UrlCheck = { ok: true; url: string; slug: string } | { ok: false; error: string };

export function checkGithubUrl(raw: string): UrlCheck {
  let value = raw.trim();
  if (!value) return { ok: false, error: "Enter a GitHub repository URL" };
  if (/^(www\.)?github\.com\//i.test(value)) value = `https://${value}`;
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return { ok: false, error: "Enter a valid URL such as https://github.com/owner/repo" };
  }
  const host = parsed.hostname.toLowerCase();
  if (parsed.protocol !== "https:" || !["github.com", "www.github.com"].includes(host) || parsed.port) {
    return { ok: false, error: "Only https://github.com repositories are supported" };
  }
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    return { ok: false, error: "Remove credentials, query strings and fragments from the URL" };
  }
  const segments = parsed.pathname.split("/").filter(Boolean);
  if (segments.length !== 2) return { ok: false, error: "Use the repository root: https://github.com/owner/repo" };
  const owner = segments[0];
  const name = segments[1].replace(/\.git$/, "");
  if (!OWNER.test(owner) || !NAME.test(name) || name.startsWith(".")) {
    return { ok: false, error: "That does not look like a valid owner/repository name" };
  }
  return { ok: true, url: `https://github.com/${owner}/${name}`, slug: `${owner}/${name}` };
}
