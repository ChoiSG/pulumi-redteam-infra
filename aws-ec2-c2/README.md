# AWS-EC2-C2 

본 플루미 Role은 AWS에 C2 서버를 EC2를 이용해 생성합니다. 

오퍼레이터마다 사용할 C2 프레임워크가 다를 수 있기 때문에, EC2 생성 및 기본적인 작전 보안 외에 다른 설정을 하지 않습니다. 

IaC 프로젝트이기 때문에 실행 전 `.env` 파일을 꼭 업데이트 해야합니다. 

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

2. 설치할 C2에 따라서 `install-c2.sh` 수정

- 혹은, 직접 SSH 해서 설치해도 무방. 그냥 내버려둬도 됨. 

- 기본 `install-c2.sh`는 오픈소스 C2 프레임워크인 Sliver를 설치합니다 (주석 삭제 필요). 

3. 실행 
```
pulumi stack init dev # 첫 실행 시 한번만 실행
pulumi preview # syntax, sanity-check 용 
pulumi up -y  # 실행! 
```

(4. 삭제/Revert)
```
pulumi destroy -y 
```

## 중요 `.env` 변수 

- AWS Credentials: 기본으로 필요합니다
- AWS Infrastructure: 리다이렉터 서버를 생성할 Region, VPC, SUBNET, SSH Key 등을 지정. AWS 콘솔에서 확인 후 복/붙 합니다. 

## 작전보안 

본 플루미 Role을 통해서 생성된 EC2는 다음과 같은 접근 제어가 되어 있습니다: 

TCP INGRESS 
- TCP/ALL - 10.0.0.0/8: AWS EC2 사설 IP에서 오는 트래픽은 모두 허용 
- TCP/22 - Operator Public IP CIDR: 오퍼레이터의 공인 IP CIDR 
- TCP/41276 - 0.0.0.0/0: 간편한 파일 업로드/다운로드를 위한 디버깅 포트 

TCP EGRESS 
- 모두 허용 