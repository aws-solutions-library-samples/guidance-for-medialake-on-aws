FROM python:3.12.9-alpine3.21
RUN apk add --no-cache aws-cli nodejs npm jq unzip curl bash

# Install AWS CDK
RUN npm install -g aws-cdk

# Install esbuild
RUN npm install -g esbuild
