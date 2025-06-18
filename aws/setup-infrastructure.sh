#!/bin/bash

# AWS 인프라 구성 스크립트
# 주의: 이 스크립트는 AWS CLI가 설치되어 있고, 적절한 권한이 있는 상태에서 실행해야 합니다.

# 환경 변수 설정
ENVIRONMENT="staging"  # staging 또는 production
REGION="us-east-1"     # AWS 리전
TIMESTAMP=$(date +%Y%m%d%H%M%S)
STACK_NAME="bluewhale-${ENVIRONMENT}-${TIMESTAMP}"
ECR_REPOSITORY_NAME="bluewhale-backend"

# VPC ID와 서브넷 ID는 AWS 콘솔에서 확인하여 입력
VPC_ID="vpc-0e3853225b6ac6f6d"  # 실제 VPC ID
SUBNET_IDS="subnet-046843e6b037e03d9,subnet-008511407e8635325,subnet-0072d3fc0edaaa3dc"  # 실제 서브넷 ID (쉼표로 구분)

# 스택 존재 여부 확인
if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION 2>/dev/null; then
    echo "스택 $STACK_NAME 업데이트 중..."
    aws cloudformation update-stack \
        --stack-name $STACK_NAME \
        --template-body file://aws/cloudformation-ecs.yml \
        --parameters \
            ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT \
            ParameterKey=ECRRepositoryName,ParameterValue=$ECR_REPOSITORY_NAME \
            ParameterKey=VpcId,ParameterValue=$VPC_ID \
            ParameterKey=SubnetIds,ParameterValue=\"$SUBNET_IDS\" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION
else
    echo "스택 $STACK_NAME 생성 중..."
    aws cloudformation create-stack \
        --stack-name $STACK_NAME \
        --template-body file://aws/cloudformation-ecs.yml \
        --parameters \
            ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT \
            ParameterKey=ECRRepositoryName,ParameterValue=$ECR_REPOSITORY_NAME \
            ParameterKey=VpcId,ParameterValue=$VPC_ID \
            ParameterKey=SubnetIds,ParameterValue=\"$SUBNET_IDS\" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region $REGION
fi

# 스택 생성/업데이트 완료 대기
echo "스택 생성/업데이트 완료 대기 중..."
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME --region $REGION || \
aws cloudformation wait stack-update-complete --stack-name $STACK_NAME --region $REGION

# 스택 출력 값 가져오기
echo "스택 출력 값 가져오기..."
CLUSTER_NAME=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ClusterName'].OutputValue" --output text)
SERVICE_NAME=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ServiceName'].OutputValue" --output text)
LOAD_BALANCER_DNS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" --output text)
ECR_REPOSITORY_URI=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryURI'].OutputValue" --output text)

echo "인프라 구성이 완료되었습니다."
echo "환경: $ENVIRONMENT"
echo "리전: $REGION"
echo "클러스터 이름: $CLUSTER_NAME"
echo "서비스 이름: $SERVICE_NAME"
echo "로드 밸런서 DNS: $LOAD_BALANCER_DNS"
echo "ECR 저장소 URI: $ECR_REPOSITORY_URI"

# GitHub Actions 시크릿 설정 안내
echo ""
echo "GitHub Actions 시크릿 설정 안내:"
echo "다음 값들을 GitHub 저장소의 시크릿으로 설정하세요."
echo "AWS_ACCESS_KEY_ID: <AWS 액세스 키 ID>"
echo "AWS_SECRET_ACCESS_KEY: <AWS 시크릿 액세스 키>"
echo "AWS_REGION: $REGION"
echo "ECR_REPOSITORY: $ECR_REPOSITORY_NAME"
if [ "$ENVIRONMENT" = "staging" ]; then
  echo "STAGING_ECS_CLUSTER: $CLUSTER_NAME"
  echo "STAGING_ECS_SERVICE: $SERVICE_NAME"
  echo "STAGING_API_URL: http://$LOAD_BALANCER_DNS"
else
  echo "PROD_ECS_CLUSTER: $CLUSTER_NAME"
  echo "PROD_ECS_SERVICE: $SERVICE_NAME"
  echo "PROD_API_URL: http://$LOAD_BALANCER_DNS"
fi
