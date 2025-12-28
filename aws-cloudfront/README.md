# AWS-Cloudfront

본 플루미 Role은 AWS에 Cloudfront Distribution을 생성합니다. 

리다이렉터 서버 앞에 CDN을 놓기 때문에 대상의 내부망에서 EGRESS시 `<random>.cloudfront.net` 도메인으로 나가게 되어 프록시/DPI 통과 확률을 높입니다. 

## 사용법

0. 의존성 설치 
```
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

1. `.env.example` 파일 업데이트 이후 `.env` 로 파일 이름 변경 

- env 파일의 AWS 관련 정보 (VPC ID, Subnet ID, SSH Key Name, 등) 및 다양한 정보를 업데이트 합니다 

```
# 파일 수정... 
vim .env.example 

# 파일 이름 변경 
mv .env.example .env 
```

2. 실행 
```
pulumi stack init dev # 첫 실행 시 한번만 실행
pulumi preview # syntax, sanity-check 용 
pulumi up -y  # 실행! 
```

(3. 삭제/Revert)
```
pulumi destroy -y 
```

## 중요 `.env` 변수 

- AWS Credentials: 기본으로 필요합니다
- CloudFront Distribution Configuration: Cloudfront 이름 지정 
- Redirector Origin Configuration: 리다이렉터 서버의 FQDN/DNS A 레코드 지정 
- Price Class: 그냥 PriceClass_100이 제일 쌈 
    - 속도가 문제라면 PriceClass_200 지정 
