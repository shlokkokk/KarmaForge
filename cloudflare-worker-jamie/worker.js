export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = "old.reddit.com";

    // Reconstruct request with the target host header
    const headers = new Headers(request.headers);
    headers.set("Host", "old.reddit.com");

    const newReq = new Request(url.toString(), {
      method: request.method,
      headers: headers,
      body: request.body,
      redirect: "follow"
    });

    return fetch(newReq);
  }
};
