# Mustang CLI (Apache-2.0): validates ZUGFeRD / Factur-X PDFs (incl. PDF/A-3 via veraPDF)
# and XML (ZUGFeRD profiles, XRechnung CII and UBL). CLI only: used one-shot for the
# validator comparison (ADR 0003), not as a long-running service.

FROM alpine:3.22 AS fetch
ARG MUSTANG_VERSION=2.26.0
ARG MUSTANG_SHA256=42d7868cb68264874a7b8cab4c3587b03b23ccc7cd72373da917f66758bb9736
RUN apk add --no-cache curl
WORKDIR /dl
RUN curl -fsSL -o mustang.jar \
      "https://github.com/ZUGFeRD/mustangproject/releases/download/core-${MUSTANG_VERSION}/Mustang-CLI-${MUSTANG_VERSION}.jar" \
 && echo "${MUSTANG_SHA256}  mustang.jar" | sha256sum -c -

FROM eclipse-temurin:21-jre
RUN groupadd --system validator && useradd --system --gid validator --create-home --home-dir /opt/mustang validator
WORKDIR /opt/mustang
COPY --from=fetch --chown=validator:validator /dl/mustang.jar /opt/mustang/mustang.jar
USER validator
ENTRYPOINT ["java", "-Xmx1g", "-Dfile.encoding=UTF-8", "-jar", "/opt/mustang/mustang.jar", "--no-notices"]
