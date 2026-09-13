# Reference platform is linux/amd64. Resolve new digests deliberately and rerun evidence.
FROM eclipse-temurin:21-jdk-jammy@sha256:8878012b286ef00032346bfbdd55b10e9f5bf923430e3a85c7c3d6e6db6f4605 AS java
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
COPY --from=java /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk PATH=/opt/java/openjdk/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY labs /app/labs
COPY tests /app/tests
RUN javac /app/labs/zip-differentials/ZipProbe.java && chmod -R a+rX /app
USER 65532:65532
CMD ["python", "labs/zip-differentials/run.py"]
