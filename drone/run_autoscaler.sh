#!/bin/bash

. ./drone_settings

docker run -d \
  -e DRONE_POOL_MIN=${DRONE_POOL_MIN} \
  -e DRONE_POOL_MAX=${DRONE_POOL_MAX} \
  -e DRONE_SERVER_PROTO=${DRONE_SERVER_PROTO} \
  -e DRONE_SERVER_HOST=${DRONE_SERVER_HOST} \
  -e DRONE_SERVER_TOKEN=${DRONE_SERVER_TOKEN} \
  -e DRONE_AGENT_TOKEN=${DRONE_AGENT_TOKEN} \
  -e DRONE_AMAZON_REGION=${DRONE_AMAZON_REGION} \
  -e DRONE_AMAZON_SUBNET_ID=${DRONE_AMAZON_SUBNET_ID} \
  -e DRONE_AMAZON_SECURITY_GROUP=${DRONE_AMAZON_SECURITY_GROUP} \
  -e DRONE_AMAZON_SSHKEY=${DRONE_AMAZON_SSHKEY} \
  -e DRONE_AMAZON_INSTANCE=${DRONE_AMAZON_INSTANCE} \
  -e DRONE_AMAZON_IMAGE=${DRONE_AMAZON_IMAGE} \
  -e DRONE_AMAZON_VOLUME_SIZE=${DRONE_AMAZON_VOLUME_SIZE} \
  -e DRONE_AMAZON_USERDATA_FILE=${DRONE_AMAZON_USERDATA_FILE} \
  -e DRONE_AMAZON_IAM_PROFILE_ARN=${DRONE_AMAZON_IAM_PROFILE_ARN} \
  -e DRONE_INTERVAL=${DRONE_INTERVAL} \
  -e DRONE_AGENT_CONCURRENCY=${DRONE_AGENT_CONCURRENCY} \
  -e AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  -e AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  --volume=/home/ubuntu/drone-poc/cloud-init-custom.yml:/etc/cloud-init-custom.yml \
  -p 8080:8080 \
  --restart=always \
  --name=autoscaler \
  drone/autoscaler

