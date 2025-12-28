#!/usr/bin/env python3
"""
SSH Key Management Utility for Pulumi Red Team Infrastructure

Simple utility to generate or import SSH keys and register them with AWS EC2.
"""

import argparse
import boto3
import configparser
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path


def update_env_files(key_name, key_filepath):
    """
    Update .env or .env.example files in all role directories with SSH key information.

    Args:
        key_name: AWS SSH key pair name
        key_filepath: Absolute path to the private key file
    """
    project_root = Path(__file__).parent

    role_dirs = [d for d in project_root.iterdir() if d.is_dir() and not d.name.startswith('.')]

    for role_dir in role_dirs:
        env_file = role_dir / '.env'
        env_example_file = role_dir / '.env.example'

        target_file = env_file if env_file.exists() else env_example_file if env_example_file.exists() else None

        if not target_file:
            continue

        try:
            with open(target_file, 'r') as f:
                content = f.read()

            updated = False
            if 'AWS_SSH_KEY_NAME=' in content:
                content = re.sub(r'^AWS_SSH_KEY_NAME=.*$', f'AWS_SSH_KEY_NAME={key_name}', content, flags=re.MULTILINE)
                updated = True

            if 'SSH_KEY_FILEPATH=' in content:
                content = re.sub(r'^SSH_KEY_FILEPATH=.*$', f'SSH_KEY_FILEPATH={key_filepath}', content, flags=re.MULTILINE)
                updated = True

            if updated:
                with open(target_file, 'w') as f:
                    f.write(content)
                print(f"[+] Updated {target_file.name} for {role_dir.name}")

        except Exception:
            continue


def generate_ssh_key(region, key_name, creds):
    """
    Generate a new SSH key pair and register it with AWS EC2.

    Args:
        region: AWS region to register the key in
        key_name: Name for the AWS key pair
        creds: Tuple of (access_key_id, secret_access_key)
    """
    access_key, secret_key = creds

    sshkeys_dir = Path('sshkeys')
    private_key_path = sshkeys_dir / key_name
    public_key_path = sshkeys_dir / f'{key_name}.pub'

    if private_key_path.exists():
        print(f"[-] SSH key already exists at {private_key_path}")
        print(f"[-] Delete using \"delete\" command first")
        return

    print(f"[*] Generating SSH key pair")
    try:
        result = subprocess.run([
            'ssh-keygen', '-t', 'rsa', '-b', '4096',
            '-f', str(private_key_path),
            '-N', '',
            '-C', 'pulumi-redteam-infra'
        ], check=True, capture_output=True, text=True)

        os.chmod(private_key_path, 0o600)
        os.chmod(public_key_path, 0o644)

        print(f"[+] Generated SSH key pair")
        print(f"    Private: {private_key_path}")
        print(f"    Public:  {public_key_path}")
    except subprocess.CalledProcessError as e:
        print(f"[!] Failed to generate SSH key: {e}")
        if e.stderr:
            print(f"[!] Error: {e.stderr.strip()}")
        return

    with open(public_key_path, 'r') as f:
        public_key_material = f.read().strip()

    print(f"\n[*] Importing public key to AWS EC2 ({region})")
    try:
        ec2 = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        existing_keys = ec2.describe_key_pairs()
        for key in existing_keys['KeyPairs']:
            if key['KeyName'] == key_name:
                print(f"[!] Key pair '{key_name}' already exists in AWS")
                print(f"[!] Delete it manually first or use a different key name")
                return

        response = ec2.import_key_pair(
            KeyName=key_name,
            PublicKeyMaterial=public_key_material
        )

        print(f"[+] Imported key pair to AWS: {key_name}")
        print(f"[+] Key fingerprint: {response['KeyFingerprint']}")

        update_env_files(key_name, str(private_key_path.absolute()))

        print(f"\n[+] Success! Use these values in your .env files:")
        print(f"    AWS_SSH_KEY_NAME={key_name}")
        print(f"    SSH_KEY_FILEPATH={private_key_path.absolute()}")

    except Exception as e:
        print(f"[!] Failed to import key to AWS: {e}")
        return


def import_ssh_key(key_filepath, region, key_name, creds):
    """
    Import an existing SSH key and register it with AWS EC2.

    Args:
        key_filepath: Path to existing private key file
        region: AWS region to register the key in
        key_name: Name for the AWS key pair
        creds: Tuple of (access_key_id, secret_access_key)
    """
    access_key, secret_key = creds

    private_key_path = Path(key_filepath)
    if not private_key_path.exists():
        print(f"[!] Private key file not found: {key_filepath}")
        return

    public_key_path = Path(f"{key_filepath}.pub")
    if not public_key_path.exists():
        print(f"[!] Public key file not found: {public_key_path}")
        print(f"[!] Expected public key at: {public_key_path}")
        return

    if not key_name:
        key_name = private_key_path.name

    print(f"[*] Importing SSH key from: {key_filepath}")
    print(f"[*] Using key name: {key_name}")
    print(f"[*] Target AWS region: {region}")

    with open(public_key_path, 'r') as f:
        public_key_material = f.read().strip()

    try:
        ec2 = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        existing_keys = ec2.describe_key_pairs()
        for key in existing_keys['KeyPairs']:
            if key['KeyName'] == key_name:
                print(f"[!] Key pair '{key_name}' already exists in AWS")
                print(f"[!] Delete it manually first or use a different key name")
                return

        response = ec2.import_key_pair(
            KeyName=key_name,
            PublicKeyMaterial=public_key_material
        )

        print(f"[+] Imported key pair to AWS: {key_name}")
        print(f"[+] Key fingerprint: {response['KeyFingerprint']}")

        update_env_files(key_name, str(private_key_path.absolute()))

        print(f"\n[+] Success! Use these values in your .env files:")
        print(f"    AWS_SSH_KEY_NAME={key_name}")
        print(f"    SSH_KEY_FILEPATH={private_key_path.absolute()}")

    except Exception as e:
        print(f"[!] Failed to import key to AWS: {e}")
        return


def delete_ssh_key(region, key_name, creds):
    """
    Delete SSH key from AWS EC2 and filesystem.

    Args:
        region: AWS region where the key is registered
        key_name: Name of the AWS key pair to delete
        creds: Tuple of (access_key_id, secret_access_key)
    """
    access_key, secret_key = creds

    sshkeys_dir = Path('sshkeys')
    private_key_path = sshkeys_dir / key_name
    public_key_path = sshkeys_dir / f'{key_name}.pub'

    print(f"[*] Deleting key pair '{key_name}' from AWS EC2 ({region})")
    try:
        ec2 = boto3.client(
            'ec2',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        try:
            ec2.delete_key_pair(KeyName=key_name)
            print(f"[+] Deleted key pair from AWS: {key_name}")
        except ec2.exceptions.ClientError as e:
            if 'InvalidKeyPair.NotFound' in str(e):
                print(f"[!] Key pair '{key_name}' not found in AWS")
            else:
                raise

    except Exception as e:
        print(f"[!] Failed to delete key from AWS: {e}")

    if private_key_path and private_key_path.exists():
        private_key_path.unlink()
        print(f"[+] Deleted private key: {private_key_path}")
    else:
        print(f"[!] Private key not found: {private_key_path}")

    if public_key_path and public_key_path.exists():
        public_key_path.unlink()
        print(f"[+] Deleted public key: {public_key_path}")
    else:
        print(f"[!] Public key not found: {public_key_path}")


def get_aws_credentials(cli_access_key=None, cli_secret_key=None):
    """
    Get AWS credentials from ~/.aws/credentials or CLI arguments.

    Args:
        cli_access_key: AWS Access Key ID from CLI
        cli_secret_key: AWS Secret Access Key from CLI

    Returns:
        tuple: (access_key_id, secret_access_key) or None if failed
    """
    aws_creds_path = Path.home() / '.aws' / 'credentials'

    if aws_creds_path.exists():
        try:
            config = configparser.ConfigParser()
            config.read(aws_creds_path)

            if 'default' in config:
                access_key = config['default'].get('aws_access_key_id', '').strip()
                secret_key = config['default'].get('aws_secret_access_key', '').strip()

                if access_key and secret_key:
                    print("[+] Loaded credentials from ~/.aws/credentials")
                    return (access_key, secret_key)
        except Exception as e:
            print(f"[!] Error reading credentials: {e}")

    if cli_access_key and cli_secret_key:
        print("[+] Using credentials from CLI arguments")
        return (cli_access_key, cli_secret_key)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="SSH Key Management for Pulumi RT Infra",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a new SSH key
  python3 sshkey.py generate -r ap-northeast-2 -n pulumi-rtinfra

  # Import an existing SSH key
  python3 sshkey.py file -f ~/.ssh/existing-key.pem -r ap-northeast-2 -n pulumi-rtinfra

  # Delete SSH key from AWS and filesystem (./sshkeys)
  python3 sshkey.py delete -r ap-northeast-2 -n pulumi-rtinfra

  # Use explicit AWS credentials
  python3 sshkey.py generate -r ap-northeast-2 -a AKIAICCCCAABBEXAMPLE -s wJalEXAMPLEKEY/K7MDENG/bPBBaaAAEXAMPLEKEY
        """
    )

    parser.add_argument('-a', '--access-key', help='AWS Access Key ID')
    parser.add_argument('-s', '--secret-key', help='AWS Secret Access Key')

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    generate_parser = subparsers.add_parser('generate', help='Generate a new SSH key')
    generate_parser.add_argument('-r', '--region', default='ap-northeast-2', required=True,
                                help='AWS region (e.g., ap-northeast-2)')
    generate_parser.add_argument('-n', '--name', default='pulumi-rtinfra',
                                help='AWS key pair name (default: pulumi-rtinfra)')

    file_parser = subparsers.add_parser('file', help='Import an existing SSH key')
    file_parser.add_argument('-f', '--file', required=True,
                            help='Path to existing private key file')
    file_parser.add_argument('-r', '--region', required=True,
                            help='AWS region (e.g., ap-northeast-2)')
    file_parser.add_argument('-n', '--name', default='pulumi-rtinfra',
                            help='AWS key pair name (default: pulumi-rtinfra)')

    delete_parser = subparsers.add_parser('delete', help='Delete SSH key from AWS and filesystem')
    delete_parser.add_argument('-r', '--region', required=True,
                              help='AWS region (e.g., ap-northeast-2)')
    delete_parser.add_argument('-n', '--name', default='pulumi-rtinfra',
                              help='AWS key pair name (default: pulumi-rtinfra)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    creds = get_aws_credentials(args.access_key, args.secret_key)
    if not creds:
        print("[!] Failed to get AWS credentials")
        print("[!] Please configure ~/.aws/credentials or use -a and -s flags")
        sys.exit(1)

    if args.command == 'generate':
        generate_ssh_key(args.region, args.name, creds)
    elif args.command == 'file':
        import_ssh_key(args.file, args.region, args.name, creds)
    elif args.command == 'delete':
        delete_ssh_key(args.region, args.name, creds)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
