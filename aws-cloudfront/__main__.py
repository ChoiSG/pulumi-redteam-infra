import os
import pulumi
import pulumi_aws as aws
from dotenv import load_dotenv

################################################
################### SETUP ######################
################################################

# Load vars from .env
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

###############################################
################### MAIN ######################
###############################################

# Create Cloudfront Distribution 
distribution = aws.cloudfront.Distribution("cdn-distribution",
    enabled=True,
    comment=CLOUDFRONT_COMMENT,

    # Origin configuration -> points to redirector domain
    origins=[
        aws.cloudfront.DistributionOriginArgs(
            domain_name=REDIRECTOR_DOMAIN,
            origin_id="redirector-origin",
            custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                http_port=80,
                https_port=443,
                origin_protocol_policy="match-viewer",  
                origin_ssl_protocols=["TLSv1"], 
                origin_keepalive_timeout=5,
                origin_read_timeout=30,
            ),
            # Custom header to identify CloudFront traffic at origin
            custom_headers=[
                aws.cloudfront.DistributionOriginCustomHeaderArgs(
                    name="cloudfront",
                    value="true",
                )
            ],
        )
    ],

    # Cache behavior
    default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
        target_origin_id="redirector-origin",
        viewer_protocol_policy="redirect-to-https",  
        allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
        cached_methods=["GET", "HEAD"],  

        # NO caching - all TTLs set to 0
        min_ttl=0,
        default_ttl=0,
        max_ttl=0,

        # Legacy cache settings - Forward ALL headers, query strings, and cookies
        forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
            query_string=True,  
            headers=["*"],  
            cookies=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesCookiesArgs(
                forward="all", 
            ),
        ),

        compress=False,
    ),

    # No restrictions
    restrictions=aws.cloudfront.DistributionRestrictionsArgs(
        geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
            restriction_type="none",
        ),
    ),

    # SSL/TLS certificate configuration
    viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
        cloudfront_default_certificate=True, 
        minimum_protocol_version="TLSv1",
        ssl_support_method="sni-only",
    ),

    # Price class - use PriceClass_All for global, PriceClass_100 for cheaper
    price_class=os.getenv("CLOUDFRONT_PRICE_CLASS", "PriceClass_100"),

    is_ipv6_enabled=True,

    tags={
        "Name": CLOUDFRONT_DISTRIBUTION_NAME
    },

    opts=pulumi.ResourceOptions(provider=aws_provider)
)

# Export important details
pulumi.export("distribution_id", distribution.id)
pulumi.export("distribution_arn", distribution.arn)
pulumi.export("distribution_domain_name", distribution.domain_name)
pulumi.export("distribution_hosted_zone_id", distribution.hosted_zone_id)
pulumi.export("distribution_status", distribution.status)
