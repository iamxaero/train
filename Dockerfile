FROM python:3.10.0

RUN mkdir -p /train

WORKDIR /train

COPY . /train

# hadolint ignore=DL3042,DL3025,DL3013
RUN pip3 install --upgrade \
        pip==20.0.2 \
        setuptools==41.6.0 && \
        pip3 install \
        python_gitlab \
        PyYAML \ 
        json-logging

# hadolint ignore=DL3025
CMD [ python /train/train.py ]
