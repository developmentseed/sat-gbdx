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

# Install some complements to work
RUN curl https://rpm.nodesource.com/setup_8.x | bash -
RUN yum install -y nodejs
RUN git clone -b dev https://github.com/Rub21/geokit && cd geokit && npm link

WORKDIR /home/geolambda
