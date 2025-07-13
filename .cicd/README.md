# CI/CD pipeline

## Building a custom image for Gitlab CI

Building a custom image will speed up every build and deployment

Follow the instruction in the link bellow to create an authentication token
https://docs.gitlab.com/ee/user/packages/container_registry/

Then run the following commands to build and push your new Docker image

```
echo "<GITLAB TOKEN>" | docker login registry.gitlab.aws.dev -u <GITLAB USER> --password-stdin
docker build --platform linux/amd64 -t registry.gitlab.aws.dev/<GITLAB GROUP>/<GITLAB PROJECT> .
docker push registry.gitlab.aws.dev/<GITLAB GROUP>/<GITLAB PROJECT>
```
