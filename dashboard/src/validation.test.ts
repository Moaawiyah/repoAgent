import { describe, expect, it } from "vitest";
import { checkGithubUrl } from "./validation";

describe("checkGithubUrl", () => {
  it.each([
    ["https://github.com/psf/requests", "psf/requests"],
    ["github.com/psf/requests.git", "psf/requests"],
    ["  https://www.github.com/a-b/c_d.e/ ", "a-b/c_d.e"],
  ])("accepts %s", (raw, slug) => {
    const check = checkGithubUrl(raw);
    expect(check).toMatchObject({ ok: true, slug, url: `https://github.com/${slug}` });
  });

  it.each([
    "", "not a url", "http://github.com/o/r", "https://gitlab.com/o/r", "https://github.com/o",
    "https://github.com/o/r/tree/main", "https://github.com/o/r?x=1", "https://github.com/o/r#x",
    "https://user:pw@github.com/o/r", "https://github.com:8443/o/r", "https://github.com/-o/r",
    "https://github.com/o/.hidden", "file:///etc/passwd", "git@github.com:o/r.git",
  ])("rejects %j", (raw) => {
    const check = checkGithubUrl(raw);
    expect(check.ok).toBe(false);
    if (!check.ok) expect(check.error.length).toBeGreaterThan(5);
  });
});
