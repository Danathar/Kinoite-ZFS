FROM ghcr.io/myoung34/docker-github-actions-runner:ubuntu-noble

RUN cp -a /actions-runner /opt/actions-runner-image

COPY ci/github-runner/runner-entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh
