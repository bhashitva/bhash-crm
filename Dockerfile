FROM eclipse-temurin:17-jdk-jammy AS build
WORKDIR /source
COPY . .
RUN sh build.sh && mkdir -p target/healthcheck && javac -d target/healthcheck deploy/Healthcheck.java

FROM eclipse-temurin:17-jre-jammy
RUN groupadd --gid 10001 crm && useradd --uid 10001 --gid crm --no-create-home crm \
    && mkdir -p /app /data && chown crm:crm /data
WORKDIR /app
COPY --from=build --chown=10001:10001 /source/target/crm.jar /app/crm.jar
COPY --from=build --chown=10001:10001 /source/target/healthcheck /app/healthcheck
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=8s --start-period=30s --retries=3 \
    CMD ["java", "-Djdk.httpclient.allowRestrictedHeaders=host", "-cp", "/app/healthcheck", "Healthcheck"]
ENTRYPOINT ["java", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8", "-jar", "/app/crm.jar"]
CMD ["--bind=0.0.0.0", "--port=8080", "--db=/data/crm.db", "--origin=https://bhashcrm.bhashitva.org"]
