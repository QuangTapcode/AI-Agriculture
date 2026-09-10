const ORIGIN_URL = "https://work-developing-developers-occupation.trycloudflare.com";

export default {
  async fetch(request) {
    const incomingUrl = new URL(request.url);
    const upstreamUrl = new URL(ORIGIN_URL);
    upstreamUrl.pathname = incomingUrl.pathname;
    upstreamUrl.search = incomingUrl.search;

    try {
      return await fetch(new Request(upstreamUrl, request));
    } catch {
      return new Response("AgriAI tam thoi khong ket noi duoc may chu.", {
        status: 502,
        headers: { "content-type": "text/plain; charset=utf-8" },
      });
    }
  },
};
