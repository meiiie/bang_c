const DEFAULT_RELEASE_TAG = "v0.3.1";
const DEFAULT_REPO_RAW_BASE = "https://raw.githubusercontent.com/meiiie/bang_c";
const DEFAULT_GITHUB_URL = "https://github.com/meiiie/bang_c";

function redirect(location, status = 302) {
  return new Response(null, {
    status,
    headers: {
      Location: location,
      "Cache-Control": status === 301 ? "public, max-age=3600" : "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const releaseTag = env.NEKO_RELEASE_TAG || DEFAULT_RELEASE_TAG;
    const rawBase = env.NEKO_REPO_RAW_BASE || DEFAULT_REPO_RAW_BASE;
    const githubUrl = env.NEKO_GITHUB_URL || DEFAULT_GITHUB_URL;

    if (url.pathname === "/" || url.pathname === "") {
      return redirect(githubUrl, 302);
    }

    if (url.pathname === "/install.ps1") {
      return redirect(`${rawBase}/${releaseTag}/install.ps1`, 302);
    }

    if (url.pathname === "/install.sh") {
      return redirect(`${rawBase}/${releaseTag}/install.sh`, 302);
    }

    if (url.pathname === "/main/install.ps1") {
      return redirect(`${rawBase}/main/install.ps1`, 302);
    }

    if (url.pathname === "/main/install.sh") {
      return redirect(`${rawBase}/main/install.sh`, 302);
    }

    return new Response("Not found", {
      status: 404,
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "X-Content-Type-Options": "nosniff",
      },
    });
  },
};
