import os
import pulumi
import pulumi_aws as aws
import pulumi_command as command
from dotenv import load_dotenv

################################################
################### SETUP ######################
################################################

# Loading Environment Vars from .env
load_dotenv()
for key, value in os.environ.items():
    globals()[key] = value
    # print(f"[+] Env Key: {key}, Value: {value}")

# AWS Provider
aws_provider = aws.Provider("aws-provider",
    region=AWS_REGION,
    access_key=AWS_ACCESS_KEY,
    secret_key=AWS_SECRET_KEY,
)

# Parse operator IPs (supports comma-separated list)
operator_cidrs = [cidr.strip() for cidr in OPERATOR_PUBLIC_IP_CIDR.split(',')]

# Setup script asset
setup_script_asset = pulumi.FileAsset("install-c2.sh")

###############################################
################### MAIN ######################
###############################################

# 1. Create security group for C2 server
c2_sg = aws.ec2.SecurityGroup("pulumi-c2-sg",
    description="SG for pulumi generated C2 server - SSH from operator, all traffic from EC2 private network, and TCP 41276 from anywhere",
    vpc_id=AWS_VPC_ID,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=22,
            to_port=22,
            cidr_blocks=operator_cidrs,
            description="SSH from operator"
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=0,
            to_port=65535,
            cidr_blocks=["10.0.0.0/8"],
            description="All TCP from private network"
        ),
        aws.ec2.SecurityGroupIngressArgs(
            protocol="tcp",
            from_port=41276,
            to_port=41276,
            cidr_blocks=["0.0.0.0/0"],
            description="C2 temp download port for shellcode/payload download "
        ),
    ],
    egress=[
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

# 2. Create an EC2 instance for C2
instance = aws.ec2.Instance("c2-instance",
    tags={"Name": AWS_EC2_NAME},
    instance_type=AWS_EC2_TYPE,
    ami=AWS_AMI,
    key_name=AWS_SSH_KEY_NAME,
    subnet_id=AWS_SUBNET_ID,
    vpc_security_group_ids=[c2_sg.id],
    associate_public_ip_address=True,
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        volume_size=int(AWS_ROOT_VOLUME_SIZE_GB),
        volume_type="gp3",
        delete_on_termination=True,
    ),
    opts=pulumi.ResourceOptions(provider=aws_provider)
)

# 3. Setup remote connection
default_connection = command.remote.ConnectionArgs(
    host=instance.public_ip,
    user="ubuntu",
    private_key=open(SSH_KEY_FILEPATH).read(),
)

# Wait for instance to be reachable
instance_ready = command.remote.Command("instance-ready",
    connection=default_connection,
    create="echo Instance is ready",
    opts=pulumi.ResourceOptions(depends_on=[instance])
)

# 4. Copy and run setup script
copy_setup_script = command.remote.CopyToRemote("copy-setup-script",
    connection=default_connection,
    source=setup_script_asset,
    remote_path="/tmp/install-c2.sh",
    opts=pulumi.ResourceOptions(depends_on=[instance_ready])
)

run_setup = command.remote.Command("run-setup",
    connection=default_connection,
    create="chmod +x /tmp/install-c2.sh && sudo /tmp/install-c2.sh",
    opts=pulumi.ResourceOptions(depends_on=[copy_setup_script])
)

# Cleanup - remove the setup script
cleanup = command.remote.Command("cleanup",
    connection=default_connection,
    create="rm -f /tmp/install-c2.sh",
    opts=pulumi.ResourceOptions(depends_on=[run_setup])
)

# Export important details
pulumi.export("instance_id", instance.id)
pulumi.export("instance_public_ip", instance.public_ip)
pulumi.export("instance_private_ip", instance.private_ip)
pulumi.export("SSH", pulumi.Output.format("ssh -i {0} ubuntu@{1}", SSH_KEY_FILEPATH, instance.public_ip))
pulumi.export("DONE", "SSH in and finish setting up your C2 framework")