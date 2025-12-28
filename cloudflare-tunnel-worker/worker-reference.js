(() => {
    // # UPDATE ME # Hardcoding Section. 
    const WORKER_ENDPOINT = "https://REDACTED.REDACTED.workers.dev";
    const SLIVER_ENDPOINT = "https://REDACTED.REDACTED.com";
    const SERVICE_CF_ID = "REDACTED.access";
    const SERVICE_CF_SECRET = "REDACTED";
    const SLIVER_HEADER_NAME = ["Header-1", "Header-2"];    // Single entry is also fine 
    const SLIVER_HEADER_VALUE = ["Value-1", "Value-2"];     // Single entry is also fine 
    const SLIVER_UA = "CustomUserAgentValue";

    addEventListener("fetch", (event) => {
        event.respondWith(handleRequest(event));
    });

    async function handleRequest(event) {
        const req = event.request;

        // Safety Check 1 - HTTP Header name + value 
        for (let i = 0; i < SLIVER_HEADER_NAME.length; i++) {
            const headerName = SLIVER_HEADER_NAME[i];
            const headerValue = SLIVER_HEADER_VALUE[i];
            const reqHeaderValue = req.headers.get(headerName);

            if (!reqHeaderValue || reqHeaderValue !== headerValue) {
                return new Response("Forbidden", { status: 403 });
            }
        }

        // Safety Check 2 - User Agent check 
        const userAgent = req.headers.get("User-Agent");
        if (!userAgent || userAgent !== SLIVER_UA) {
            return new Response("Forbidden", { status: 403 });
        }

        // Build request
        const path = req.url.replace(WORKER_ENDPOINT, "");
        const sliverUrl = SLIVER_ENDPOINT + path;
        const modifiedHeaders = new Headers(req.headers);

        // If incoming client/agent is already authenticated, do NOT add service tokens again since that will 
        // indefinitely create duplicated CF_Authorization cookies to the point of 400 Bad Request. 
        const incomingCookie = req.headers.get("Cookie") || "";
        if (!incomingCookie.includes("CF_Authorization=")) {
            modifiedHeaders.set("CF-Access-Client-Id", SERVICE_CF_ID);
            modifiedHeaders.set("CF-Access-Client-Secret", SERVICE_CF_SECRET);
        } else {
            modifiedHeaders.delete("CF-Access-Client-Id");
            modifiedHeaders.delete("CF-Access-Client-Secret");
        }

        const sliverRequest = new Request(sliverUrl, {
            method: req.method,
            headers: modifiedHeaders,
            body: req.body,
        });

        const sliverResponse = await fetch(sliverRequest);

        return sliverResponse;
    }
})();