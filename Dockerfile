FROM --platform=linux/amd64 python:3.11-slim-buster as base

COPY . /code/
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

CMD ["python3", "/code/src/__main__.py"]
