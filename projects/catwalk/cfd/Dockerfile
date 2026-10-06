FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=secret,id=ca_bundle,target=/run/ca-bundle.pem,mode=0444,required=true \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get -o Acquire::https::CaInfo=/run/ca-bundle.pem update && \
    apt-get -o Acquire::https::CaInfo=/run/ca-bundle.pem install -y --no-install-recommends \
      openfoam gmsh python3-gmsh python3-numpy python3-scipy ca-certificates && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /work
