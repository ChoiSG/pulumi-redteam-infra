import os
import atexit
import pulumi
import pulumi_aws as aws
import pulumi_command as command
import pulumi_cloudflare as cloudflare 
from dotenv import load_dotenv

################################################
################### SETUP ######################
################################################

# Load vars from .env
load_dotenv()
for key, value in os.environ.items():
    globals()[key] = value
    # print(f"[+] Env Key: {key}, Value: {value}")

# Validate DNS_PROVIDER
DNS_PROVIDER = os.getenv("DNS_PROVIDER", "cloudflare")
if DNS_PROVIDER not in ["cloudflare", "route53"]:
    raise ValueError("DNS_PROVIDER must be either 'cloudflare' or 'route53'")

# Check if Elastic IP should be used
USE_ELASTIC_IP = os.getenv("USE_ELASTIC_IP", "false").lower() == "true"

# Get root volume size with default
AWS_ROOT_VOLUME_SIZE_GB = os.getenv("AWS_ROOT_VOLUME_SIZE_GB", "12")

# Parse operator IPs (supports comma-separated list)
operator_cidrs = [cidr.strip() for cidr in OPERATOR_PUBLIC_IP_CIDR.split(',')]

# Providers
aws_provider = aws.Provider("aws-provider",
    region=AWS_REGION,
    access_key=AWS_ACCESS_KEY,
    secret_key=AWS_SECRET_KEY,
)

# Only create Cloudflare provider if DNS_PROVIDER is cloudflare
cf_provider = None
if DNS_PROVIDER == "cloudflare":
    CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")
    if not CLOUDFLARE_API_TOKEN:
        raise ValueError("CLOUDFLARE_API_TOKEN is required when DNS_PROVIDER is cloudflare")
    cf_provider = cloudflare.Provider("cf-provider", api_token=CLOUDFLARE_API_TOKEN)

###############################################
############## Template Updates ###############
###############################################

# Bash script for redirector server setup 
setup_script_asset = pulumi.FileAsset("redirector-nginx.sh")

# Nginx configuration file update 
with open("nginx.conf.template", "r") as f:
    nginx_config_template = f.read()

nginx_config = nginx_config_template.replace("${DOMAIN}", DNS_DOMAIN)
nginx_config = nginx_config.replace("${C2_URL}", REDIRECTOR_C2_URL)

temp_nginx_path = "nginx.conf.generated"
with open(temp_nginx_path, "w") as f:
    f.write(nginx_config)

nginx_config_asset = pulumi.FileAsset(temp_nginx_path)

atexit.register(lambda: os.remove(temp_nginx_path) if os.path.exists(temp_nginx_path) else None)

###############################################
################### MAIN ######################
###############################################

# 1. Create security group for redirector
redirector_sg = aws.ec2.SecurityGroup("pulumi-redirector-sg",
    description="Security group for pulumi generated redirector server - allows HTTPS/HTTP from anywhere, SSH from operator",
    vpc_id=AWS_VPC_ID,
    ingress=[
        # HTTPS from anywhere
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=443,
            to_port=443,
            cidr_blocks=["0.0.0.0/0"],
            description="HTTPS from anywhere"
        ),
        # HTTP from anywhere
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=80,
            to_port=80,
            cidr_blocks=["0.0.0.0/0"],
            description="HTTP from anywhere"
        ),
        # SSH from operator only
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=operator_cidrs,
            description="SSH from operator"
        ),
    ],
    egress=[
        # Allow all outbound traffic
        aws.ec2.SecurityGroupEgressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],
            description="Allow all outbound"
        ),
    ],
    tags={"Name": f"{AWS_EC2_NAME}-sg"},
    opts=pulumi.ResourceOptions(provider=aws_provider)
)

# 2. Create an EC2 instance
instance = aws.ec2.Instance("ec2-instance",
    tags={ "Name": AWS_EC2_NAME },
    instance_type=AWS_EC2_TYPE,
    ami=AWS_AMI,
    key_name=AWS_SSH_KEY_NAME,
    subnet_id=AWS_SUBNET_ID,
    vpc_security_group_ids=[redirector_sg.id],
    associate_public_ip_address=True,
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_size=int(AWS_ROOT_VOLUME_SIZE_GB),
        volume_type="gp3",
        delete_on_termination=True,
    ),
    opts=pulumi.ResourceOptions(provider=aws_provider)
)

# 3. Conditionally create and associate Elastic IP
if USE_ELASTIC_IP:
    eip = aws.ec2.Eip("redirector-eip",
        instance=instance.id,
        tags={"Name": f"{AWS_EC2_NAME}-eip"},
        opts=pulumi.ResourceOptions(provider=aws_provider)
    )
    public_ip = eip.public_ip
else:
    public_ip = instance.public_ip

# 4. Copy nginx config and setup script to remote
default_connection = command.remote.ConnectionArgs(
    host=public_ip,
    user="ubuntu",
    private_key=open(SSH_KEY_FILEPATH).read(),
)

instance_ready = command.remote.Command("instance-ready",
    connection=default_connection,
    create="echo Instance is ready",
    opts=pulumi.ResourceOptions(depends_on=[instance])
)

copy_nginx_config = command.remote.CopyToRemote("copy-nginx-config",
    connection=default_connection,
    source=nginx_config_asset,
    remote_path="/tmp/nginx.conf",
    opts=pulumi.ResourceOptions(depends_on=[instance_ready])
)

copy_setup_script = command.remote.CopyToRemote("copy-setup-script",
    connection=default_connection,
    source=setup_script_asset,
    remote_path="/tmp/redirector-nginx.sh",
    opts=pulumi.ResourceOptions(depends_on=[instance_ready])
)

# 5. Run nginx setup script and install nginx configuration file 
cloudflare_token = globals().get("CLOUDFLARE_API_TOKEN", "")
route53_zoneid = globals().get("AWS_ROUTE53_ZONE_ID", "")
env_vars = f'DNS_PROVIDER="{DNS_PROVIDER}" CLOUDFLARE_API_TOKEN="{cloudflare_token}" AWS_ACCESS_KEY="{AWS_ACCESS_KEY}" AWS_SECRET_KEY="{AWS_SECRET_KEY}" AWS_ROUTE53_ZONE_ID="{route53_zoneid}" DOMAIN="{DNS_DOMAIN}" AWS_REGION="{AWS_REGION}"'

run_setup = command.remote.Command("run-setup",
    connection=default_connection,
    create=f"chmod +x /tmp/redirector-nginx.sh && {env_vars} sudo -E /tmp/redirector-nginx.sh",
    opts=pulumi.ResourceOptions(depends_on=[copy_setup_script])
)

install_nginx_config = command.remote.Command("install-nginx-config",
    connection=default_connection,
    create="sudo mv /tmp/nginx.conf /etc/nginx/nginx.conf && sudo chown root:root /etc/nginx/nginx.conf && sudo chmod 644 /etc/nginx/nginx.conf && sudo systemctl restart nginx",
    opts=pulumi.ResourceOptions(depends_on=[copy_nginx_config, run_setup])
)

# 6. (Cloudflare) Create A Record 
if DNS_PROVIDER == "cloudflare":
    zones = cloudflare.get_zones(
        filter={},
        opts=pulumi.InvokeOptions(provider=cf_provider)
    )

    for zone in zones.zones:
        pulumi.log.info(f"Zone Name: {zone.name}, Zone ID: {zone.id}")

    for zone in zones.zones:
        if zone.name == DNS_DOMAIN:
            zone_id = zone.id
            break

    # Create an A record in Cloudflare
    a_record = cloudflare.Record("dns-a-record",
        zone_id=zone_id,
        name=DNS_A_RECORD,
        type="A",
        value=public_ip,
        ttl=3600,
        proxied=False,
        opts=pulumi.ResourceOptions(provider=cf_provider)
    )
    record_hostname = a_record.hostname

# 6. (Route53) Create A Record 
elif DNS_PROVIDER == "route53":
    zone = aws.route53.get_zone(name=DNS_DOMAIN, opts=pulumi.InvokeOptions(provider=aws_provider))

    a_record = aws.route53.Record("dns-a-record",
        zone_id=zone.zone_id,
        name=f"{DNS_A_RECORD}.{DNS_DOMAIN}",
        type="A",
        ttl=3600,
        records=[public_ip],
        opts=pulumi.ResourceOptions(provider=aws_provider)
    )
    record_hostname = a_record.fqdn


# Export important details
pulumi.export("instance_id", instance.id)
pulumi.export("instance_private_ip", instance.private_ip)
pulumi.export("public_ip", public_ip)
pulumi.export("using_elastic_ip", USE_ELASTIC_IP)
pulumi.export("dns_provider", DNS_PROVIDER)
pulumi.export("a_record", record_hostname)
pulumi.export("SSH", pulumi.Output.format("ssh -i {0} ubuntu@{1}", SSH_KEY_FILEPATH, public_ip))
pulumi.export("TESTING", pulumi.Output.format("curl -H 'User-Agent: redirector' https://{0}", record_hostname))
