import pulumi
import pulumi_cloudflare as cloudflare
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from .env
cloudflare_api_token = os.getenv("CLOUDFLARE_API_TOKEN")
cloudflare_account_id = os.getenv("CLOUDFLARE_ACCOUNTID")
cloudflare_zone_id = os.getenv("CLOUDFLARE_ZONEID")
tunnel_subdomain = os.getenv("TUNNEL_SUBDOMAIN")
tunnel_domain = os.getenv("TUNNEL_DOMAIN")
worker_name = os.getenv("WORKER_NAME")
worker_header_names = os.getenv("WORKER_HEADER_NAME", "").split(",")
worker_header_values = os.getenv("WORKER_HEADER_VALUE", "").split(",")
worker_user_agent = os.getenv("WORKER_USER_AGENT")

# Validate required environment variables
required_vars = {
    "CLOUDFLARE_API_TOKEN": cloudflare_api_token,
    "CLOUDFLARE_ACCOUNTID": cloudflare_account_id,
    "CLOUDFLARE_ZONEID": cloudflare_zone_id,
    "TUNNEL_SUBDOMAIN": tunnel_subdomain,
    "TUNNEL_DOMAIN": tunnel_domain,
    "WORKER_NAME": worker_name,
    "WORKER_HEADER_NAME": os.getenv("WORKER_HEADER_NAME"),
    "WORKER_HEADER_VALUE": os.getenv("WORKER_HEADER_VALUE"),
    "WORKER_USER_AGENT": worker_user_agent,
}

for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"Missing required environment variable: {var_name}")

# Fetch workers.dev subdomain from Cloudflare API
import requests
response = requests.get(
    f"https://api.cloudflare.com/client/v4/accounts/{cloudflare_account_id}/workers/subdomain",
    headers={"Authorization": f"Bearer {cloudflare_api_token}"}
)
response.raise_for_status()
worker_subdomain = response.json()["result"]["subdomain"]
print(f"[+] Fetched workers.dev subdomain: {worker_subdomain}")

# Configure Cloudflare provider
cf_provider = cloudflare.Provider(
    "cloudflare-provider",
    api_token=cloudflare_api_token,
)

# Full hostname for the tunnel
tunnel_hostname = f"{tunnel_subdomain}.{tunnel_domain}"

# ================================================================
# 1. Create Cloudflare Tunnel
# ================================================================
tunnel = cloudflare.ZeroTrustTunnelCloudflared(
    "c2-tunnel",
    account_id=cloudflare_account_id,
    name="c2-tunnel",
    secret=pulumi.Output.secret(os.urandom(32).hex()),  # Generate random 32-byte secret
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# Configure tunnel with no TLS verification (for self-signed certs on origin)
tunnel_config = cloudflare.ZeroTrustTunnelCloudflaredConfig(
    "c2-tunnel-config",
    account_id=cloudflare_account_id,
    tunnel_id=tunnel.id,
    config=cloudflare.ZeroTrustTunnelCloudflaredConfigConfigArgs(
        ingress_rules=[
            # Route all traffic to localhost (where your C2 will be running)
            cloudflare.ZeroTrustTunnelCloudflaredConfigConfigIngressRuleArgs(
                hostname=tunnel_hostname,
                service="https://localhost:443",
                origin_request=cloudflare.ZeroTrustTunnelCloudflaredConfigConfigIngressRuleOriginRequestArgs(
                    no_tls_verify=True,  # Disable TLS verification for self-signed certs
                ),
            ),
            # Catch-all rule (required by Cloudflare)
            cloudflare.ZeroTrustTunnelCloudflaredConfigConfigIngressRuleArgs(
                service="http_status:404",
            ),
        ],
    ),
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# ================================================================
# 2. Create Access Service Token (10 years)
# ================================================================
service_token = cloudflare.ZeroTrustAccessServiceToken(
    "c2-service-token",
    account_id=cloudflare_account_id,
    name="c2-tunnel-service-token",
    duration="87600h",  # 10 years
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# ================================================================
# 3. Create Access Policy (Service Auth with the service token)
# ================================================================
access_policy = cloudflare.ZeroTrustAccessPolicy(
    "c2-service-auth-policy",
    account_id=cloudflare_account_id,
    name="C2 Tunnel Service Auth Policy",
    decision="non_identity",  # Required for service tokens
    includes=[
        cloudflare.ZeroTrustAccessPolicyIncludeArgs(
            service_tokens=[service_token.id],
        ),
    ],
    session_duration="720h",  # 1 month (30 days)
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# ================================================================
# 4. Create Access Application (Self-Hosted)
# ================================================================
access_application = cloudflare.ZeroTrustAccessApplication(
    "c2-access-application",
    account_id=cloudflare_account_id,
    name="C2 Tunnel Access",
    domain=tunnel_hostname,
    type="self_hosted",
    session_duration="720h",  # 1 month
    policies=[access_policy.id],
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# ================================================================
# 5. Create DNS Record for Tunnel
# ================================================================
dns_record = cloudflare.Record(
    "c2-tunnel-dns",
    zone_id=cloudflare_zone_id,
    name=tunnel_subdomain,
    type="CNAME",
    content=tunnel.cname,
    proxied=True,  # Orange cloud - proxied through Cloudflare
    comment="Cloudflare Tunnel DNS record for C2 infrastructure",
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# ================================================================
# 6. Deploy Cloudflare Worker
# ================================================================

# Generate worker script with dynamic values
def generate_worker_script(worker_endpoint, tunnel_endpoint, service_id, service_secret, header_names, header_values, user_agent):
    # Convert Python lists to JavaScript array format
    header_names_js = '[' + ', '.join([f'"{name}"' for name in header_names]) + ']'
    header_values_js = '[' + ', '.join([f'"{value}"' for value in header_values]) + ']'

    return f"""(() => {{
    const WORKER_ENDPOINT = "{worker_endpoint}";
    const SLIVER_ENDPOINT = "{tunnel_endpoint}";
    const SERVICE_CF_ID = "{service_id}";
    const SERVICE_CF_SECRET = "{service_secret}";
    const SLIVER_HEADER_NAME = {header_names_js};
    const SLIVER_HEADER_VALUE = {header_values_js};
    const SLIVER_UA = "{user_agent}";

    addEventListener("fetch", (event) => {{
        event.respondWith(handleRequest(event));
    }});

    async function handleRequest(event) {{
        const req = event.request;

        // Safety Check 1 - HTTP Header name + value
        for (let i = 0; i < SLIVER_HEADER_NAME.length; i++) {{
            const headerName = SLIVER_HEADER_NAME[i];
            const headerValue = SLIVER_HEADER_VALUE[i];
            const reqHeaderValue = req.headers.get(headerName);

            if (!reqHeaderValue || reqHeaderValue !== headerValue) {{
                return new Response("Forbidden", {{ status: 403 }});
            }}
        }}

        // Safety Check 2 - User Agent check
        const userAgent = req.headers.get("User-Agent");
        if (!userAgent || userAgent !== SLIVER_UA) {{
            return new Response("Forbidden", {{ status: 403 }});
        }}

        // Build request
        const path = req.url.replace(WORKER_ENDPOINT, "");
        const sliverUrl = SLIVER_ENDPOINT + path;
        const modifiedHeaders = new Headers(req.headers);

        // If incoming client/agent is already authenticated, do NOT add service tokens again
        const incomingCookie = req.headers.get("Cookie") || "";
        if (!incomingCookie.includes("CF_Authorization=")) {{
            modifiedHeaders.set("CF-Access-Client-Id", SERVICE_CF_ID);
            modifiedHeaders.set("CF-Access-Client-Secret", SERVICE_CF_SECRET);
        }} else {{
            modifiedHeaders.delete("CF-Access-Client-Id");
            modifiedHeaders.delete("CF-Access-Client-Secret");
        }}

        const sliverRequest = new Request(sliverUrl, {{
            method: req.method,
            headers: modifiedHeaders,
            body: req.body,
        }});

        const sliverResponse = await fetch(sliverRequest);

        return sliverResponse;
    }}
}})();"""

# Create the worker script with values from service token and tunnel
worker_script_content = pulumi.Output.all(
    service_token.client_id,
    service_token.client_secret
).apply(lambda args: generate_worker_script(
    worker_endpoint=f"https://{worker_name}.{worker_subdomain}.workers.dev",
    tunnel_endpoint=f"https://{tunnel_hostname}",
    service_id=args[0],
    service_secret=args[1],
    header_names=worker_header_names,
    header_values=worker_header_values,
    user_agent=worker_user_agent
))

# Deploy the worker
worker = cloudflare.WorkerScript(
    "c2-proxy-worker",
    account_id=cloudflare_account_id,
    name=worker_name,
    content=worker_script_content,
    opts=pulumi.ResourceOptions(provider=cf_provider),
)

# ================================================================
# Outputs
# ================================================================
pulumi.export("tunnel_id", tunnel.id)
pulumi.export("tunnel_name", tunnel.name)
pulumi.export("tunnel_hostname", tunnel_hostname)
pulumi.export("tunnel_cname_target", tunnel.cname)
pulumi.export("dns_record_id", dns_record.id)
pulumi.export("dns_record_fqdn", dns_record.hostname)

# Service token credentials for worker.js
pulumi.export("service_token_client_id", pulumi.Output.unsecret(service_token.client_id))
pulumi.export("service_token_client_secret", pulumi.Output.unsecret(service_token.client_secret))

# Tunnel token for operators
pulumi.export("tunnel_token", pulumi.Output.unsecret(tunnel.tunnel_token))

# Worker information
pulumi.export("worker_name", worker.name)
pulumi.export("worker_url", pulumi.Output.concat("https://", worker_name, ".", worker_subdomain, ".workers.dev"))

# Generate curl test command
def generate_curl_command(worker_url, header_names, header_values, user_agent):
    header_flags = ' '.join([f'-H "{name}: {value}"' for name, value in zip(header_names, header_values)])
    return f'curl -v {header_flags} -H "User-Agent: {user_agent}" {worker_url}'

curl_test_command = generate_curl_command(
    f"https://{worker_name}.{worker_subdomain}.workers.dev",
    worker_header_names,
    worker_header_values,
    worker_user_agent
)

# Instructions for operators
pulumi.export("setup_instructions", pulumi.Output.unsecret(pulumi.Output.concat(
    "\n=== SETUP INSTRUCTIONS ===\n\n",
    "1. Access your C2 server using your preferred method (SSH/Tailscale/Wireguard/SSM)\n\n",
    "2. Install cloudflared: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64\n\n",
    "3. Run the following command to setup and start the tunnel:\n",
    "   cloudflared tunnel run --token ", tunnel.tunnel_token, "\n\n",
    "4. Your C2 infrastructure endpoints:\n",
    "   - Direct tunnel access (protected by Access): https://", tunnel_hostname, "\n",
    "   - Worker proxy (with custom headers): https://", worker_name, ".", worker_subdomain, ".workers.dev\n\n",
    "5. Test worker connectivity:\n",
    "   ", curl_test_command, "\n"
)))
