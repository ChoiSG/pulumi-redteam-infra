# Pulumi RedTeam Infra 

IaC 플랫폼인 [Pulumi](https://www.pulumi.com/)를 이용해 레드팀 공격자 인프라를 생성합니다. 

초기 세팅에 시간이 조금 들어가나, 오퍼레이터 호스트나 빌드 서버에 한번만 세팅해놓으면 계속 사용하기에 편합니다. 

## Roles 

1. aws-ec2-redirector: AWS EC2 리다이렉터 서버 생성 

2. aws-ec2-c2: AWS EC2 C2 서버 생성 

3. aws-cloudfront: AWS Cloudfront CDN 리다이렉터 생성 

(4. TODO - cloudflare-tunnel-worker)

## 초기 세팅 

플루미를 사용하기 위해서는 설치와 가입/로그인을 해야 합니다. 가입에는 GitHub/GitLab등의 OAuth을 지원하기도 합니다.  

브라우저 사용 가능한 환경이라면 계정 생성 + 로그인만 하면 되고, GUI 사용 불가한 환경이라면 가입 이후 Access Token 생성, 복/붙하면 됩니다. 

플루미 설치 + 가입/로그인  
```bash 
sudo apt update -y 
curl -fsSL https://get.pulumi.com | sh
export PATH=$PATH:$HOME/.pulumi/bin
pulumi login 
```

## 필수 요소 

플루미 설치가 끝났다면, 플루미를 프로그래매틱 하게 사용할 수 있도록 AWS IAM 유저와 SSH Key Pair를 지정 합니다. 

1. 프로그래매틱하게 AWS를 사용할 수 있는 IAM 유저 생성 후 Access/Secret Key 생성 - [예시 가이드](https://docs.aws.amazon.com/keyspaces/latest/devguide/create.keypair.html)

2. 새로운 SSH Key Pair 생성, 혹은 이미 있는 SSH Key Pair 사용 
```
# 새로운 SSH Key Pair 생성 
python3 sshkey.py generate -n pulumi-rtinfra -r ap-northeast-2 

# 혹은, 이미 갖고 있던 SSH Key Pair 사용 
python3 sshkey.py file -f ~/.ssh/id_rsa -n pulumi-rtinfra -r ap-northeast-2
```

## Pulumi Roles 사용하기 

초기 세팅과 필수 요소가 모두 갖춰졌다면, 각 Pulumi Role 디렉토리에 가서 .env 파일을 업데이트하고 사용합니다. 

각 Pulumi Role 마다 README가 있으니, 꼭 참고해주세요.

1. 원하는 Role로 이동 후 의존성 설치 
```
cd ./aws-ec2-redirector 
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

2. README.md를 바탕으로 `.env` 파일 수정
```
vim .env.example 
cp .env.example .env 
```

3. 실행 
```
pulumi stack init dev # 한번만 실행! 
pulumi preview        # Sanity check 용 테스트 
pulumi up -y          # 실제로 pulumi 실행 
```

4. Pulumi 실행 후 출력값 다시 확인 
```
pulumi stack output 
```

(5. 삭제 / Revert)
```
pulumi destroy -y     # 현 stack (dev) 안의 생성됐던 리소스 삭제 
```

# TODO 

- [x] Cloudflare workers redirector 
- [ ] C2 server + Cloudflare tunnels (with public hostname + Access protection) 
- [ ] Azure VM (redirector/c2) 
- [ ] Azure Function Apps 
- [ ] Install Tailscale / wireguard / cf tunnels for ease of access + opsec purposes 