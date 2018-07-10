FROM developmentseed/geolambda:latest

RUN \
    yum makecache fast;

ENV \
    PYCURL_SSL_LIBRARY=nss

# install requirements
WORKDIR /build
COPY requirements*txt /build/
RUN \
    pip3 install -r requirements.txt; \
    pip3 install -r requirements-dev.txt

# install app
COPY . /build
RUN \
    pip3 install . -v; \
    rm -rf /build/*;

WORKDIR /home/geolambda
