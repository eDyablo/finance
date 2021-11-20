ARG BASE_IMAGE=alpine

FROM ${BASE_IMAGE} AS build

LABEL org.opencontainers.image.authors="eyablonsky@gmail.com"

RUN apk update --no-cache \
  && apk add \
  build-base \
  postgresql-dev \
  py3-pip \
  python3-dev

WORKDIR /opt/finance

COPY requirements.txt .

RUN python3 -m venv venv \
  && source venv/bin/activate \
  && python -m pip install --upgrade pip --no-cache-dir \
  && python -m pip install --requirement requirements.txt --no-cache-dir \
  && python -m pip freeze > requirements.txt

FROM ${BASE_IMAGE} AS package

LABEL org.opencontainers.image.authors="eyablonsky@gmail.com"

RUN apk update --no-cache \
  && apk add \
  python3

WORKDIR /opt/finance

COPY --from=build /opt/finance .

COPY *.py .

CMD [ "sh", "-c", "venv/bin/python worker.py" ]
