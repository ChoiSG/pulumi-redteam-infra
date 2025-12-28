# AWS-EC2-Redirector 

본 플루미 Role은 AWS에 리다이렉터 서버를 EC2를 이용해 생성한 뒤, AWS Route53 혹은 Cloudflare를 이용해 DNS 설정 및 TLS/SSL 인증서를 설치한 nginx를 구축합니다. 

IaC 프로젝트이기 때문에 실행 전 `.env` 파일을 꼭 업데이트 해야합니다. 

## 필수 요소 

1. Route53 or Cloudflare에 등록되어 있는 공격자 도메인 

## 사용법 

0. 의존성 설치 
```
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

1. `.env.example` 파일 업데이트 이후 `.env` 로 파일 이름 변경 
```
# 파일 수정... 
vim .env.example 

# 파일 이름 변경 
mv .env.example .env 
```

2. 실행 
```
pulumi stack init dev   # 첫 실행 시 한번만 실행
pulumi preview          # syntax, sanity-check 용 
pulumi up -y            # 실행! 
```

(3. 삭제/Revert)
```
pulumi destroy -y 
```

(4. 또 다른 리다이렉터 서버 생성)
```
# 새로운 플루미 스택 생성 
pulumi stack init redirector2
pulumi up -y 
```

## Nginx 설정 파일 

본 프로젝트는 리다이렉터 서버를 생성할 뿐, 리다이렉션과 관련된 설정은 진행하지 않습니다. nginx/apache/caddy 등, 원하는 리다이렉터 서비스 설치 및 설정 파일 생성은 모두 오퍼레이터의 몫입니다. 

수동으로 해도 되고, 본 Role을 본딴 플루미 Role을 만들어 설정 파일까지 모두 자동화 해도 됩니다. 

## 중요 `.env` 변수 

- AWS Credentials: 기본으로 필요합니다

- DNS Provider: Route53 or Cloudflare 

- AWS Infrastructure: 리다이렉터 서버를 생성할 Region, VPC, SUBNET, SSH Key 등을 지정. AWS 콘솔에서 확인 후 복/붙 합니다. 한번만 설정해놓으면 됩니다.

- DNS Configuration: DNS 정보. Route53 사용할 경우 ZONE ID도 필요합니다. 

- Redirector C2 URL: Nginx가 프록시 할 C2 서버. 없다면 그냥 1.1.1.1:443 써도 됩니다. 

## 작전보안 

- 간단한 작전 보안을 위해 nginx는 HTTP User-Agent가 "redirector"로 설정된 트래픽들만 리다이렉트합니다. 그 외의 트래픽은 REDIRECT_DOMAIN으로 설정된 google.com으로 보냅니다. 

본 플루미 Role을 통해서 생성된 EC2는 다음과 같은 접근 제어가 되어 있습니다: 

TCP INGRESS 
- TCP/80/443 - 0.0.0.0/0: 인터넷에서 포트 80/443으로 들어오는 트래픽 모두 허용  
- TCP/22 - Operator Public IP CIDR: 오퍼레이터의 공인 IP CIDR 허용 

TCP EGRESS 
- 모두 허용 

## 테스트 

기본 리다이렉터는 간단한 nginx configuration을 사용합니다. User-Agent가 "redirector" 일 때 `.env`의 `REDIRECTOR_C2_URL`로 트래픽을 보내고, 아닐때에는 `nginx.conf.template`의 `REDIRECT_DOMAIN` (기본적으로 https://google.com)으로 보냅니다. 

테스트 할때에는 C2 서버 구축 후 `REDIRECTOR_C2_URL`을 업데이트 한 뒤 하는 것을 권장하지만, 성공 시 www.naver.com로 보내고(REDIRECTOR_C2_URL), 실패시 www.google.com으로 보내는 등(REDIRECT_DOMAIN)의 로직을 사용해 테스트 해도 무방합니다. 

만약 아무것도 설정하지 않고 테스트 한다면, 성공 시 한 30초 동안 대기하다가 504 Gateway Timeout 됩니다 (기본적으로 10.1.1.1:443으로 redirect 하기 때문)
```
# 성공! 
curl -k -H "User-Agent: redirector" https://subdomain.domain.com 

# 실패! 
curl -k https://subdomain.domain.com 
```