# KoSIT validator (Apache-2.0) with the XRechnung 3.0.2 configuration (Apache-2.0),
# running in daemon mode: POST raw XML to any path, 200 = accept, 406 = reject.
# Downloads are pinned by version and verified by SHA-256.

FROM alpine:3.22 AS fetch
ARG KOSIT_VERSION=1.6.3
ARG KOSIT_SHA256=799e64befca97d4080e03608c80b85dd5a5ecc5f4ae4f35d1116ec2855b9a7c9
ARG XR_TAG=v2026-08-31
ARG XR_ZIP=xrechnung-3.0.2-validator-configuration-2026-08-31.zip
ARG XR_SHA256=2530cd107c414511c5d0462ec10f886910395abfca820db82e83d70bf01221a8
RUN apk add --no-cache curl unzip
WORKDIR /dl
RUN curl -fsSL -o validator.jar \
      "https://github.com/itplr-kosit/validator/releases/download/v${KOSIT_VERSION}/validator-${KOSIT_VERSION}-standalone.jar" \
 && echo "${KOSIT_SHA256}  validator.jar" | sha256sum -c - \
 && curl -fsSL -o config.zip \
      "https://github.com/itplr-kosit/validator-configuration-xrechnung/releases/download/${XR_TAG}/${XR_ZIP}" \
 && echo "${XR_SHA256}  config.zip" | sha256sum -c - \
 && mkdir config && unzip -q config.zip -d config

FROM eclipse-temurin:21-jre
RUN groupadd --system validator && useradd --system --gid validator --home /opt/kosit validator
WORKDIR /opt/kosit
COPY --from=fetch --chown=validator:validator /dl/validator.jar /opt/kosit/validator.jar
COPY --from=fetch --chown=validator:validator /dl/config /opt/kosit/config
USER validator
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD ["bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/8080 && printf 'GET /server/health HTTP/1.0\\r\\n\\r\\n' >&3 && grep -q UP <&3"]
ENTRYPOINT ["java", "-Xmx768m", "-jar", "/opt/kosit/validator.jar", \
            "-s", "/opt/kosit/config/scenarios.xml", "-r", "/opt/kosit/config", \
            "-D", "-H", "0.0.0.0", "-P", "8080", "--disable-gui"]
